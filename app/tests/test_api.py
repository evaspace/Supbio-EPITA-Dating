from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient
from backend.main import create_app

@pytest.fixture()
def clients():
    with TemporaryDirectory() as tmp:
        app = create_app(f"sqlite:///{Path(tmp) / 'test.db'}", dev_otp=True)
        with TestClient(app, headers={"X-Campus-Request":"1"}) as alice, TestClient(app, headers={"X-Campus-Request":"1"}) as bob, TestClient(app, headers={"X-Campus-Request":"1"}) as stranger:
            yield alice, bob, stranger

def enroll(client, email, school, name, birthday="2000-05-05", gender="Non précisé"):
    otp = client.post("/api/auth/request-code", json={"email": email, "school": school})
    assert otp.status_code == 200, otp.text
    code = otp.json()["local_demo_code"]
    r = client.post('/api/auth/verify-code', json={
        "email": email, "code": code, "school": school, "name": name,
        "birthday": birthday, "city": "Paris", "gender": gender, "adult_consent": True, "password": "correct horse battery"
    })
    assert r.status_code == 200, r.text
    return r.json()["user"]

def test_auth_domains_otp_18_plus_and_private_session(clients):
    alice, bob, _ = clients
    assert alice.get('/api/me').status_code == 401
    assert alice.post('/api/auth/request-code', json={"email":"person@gmail.com","school":"EPITA"}).status_code == 422
    x = alice.post('/api/auth/request-code', json={"email":"person@epita.fr","school":"EPITA"})
    assert x.status_code == 200
    assert alice.post('/api/auth/request-code', json={"email":"person@epita.fr","school":"EPITA"}).status_code == 429
    code = x.json()['local_demo_code']
    base = {"email":"person@epita.fr","school":"EPITA","name":"Robin", "city":"Paris", "gender":"Homme","adult_consent":True,"password":"correct horse battery"}
    assert alice.post('/api/auth/verify-code',json={**base,"code":code,"birthday":"2012-06-01"}).status_code == 403
    assert alice.post('/api/auth/verify-code',json={**base,"code":"999999","birthday":"2000-06-01"}).status_code == 400
    assert alice.post('/api/auth/verify-code',json={**base,"code":code,"birthday":"2000-06-01"}).status_code == 200
    assert alice.get('/api/me').json()['email']=='person@epita.fr'
    assert bob.get('/api/me').status_code==401
    assert alice.post('/api/auth/logout').status_code==200
    assert alice.get('/api/me').status_code == 401

def test_match_chat_block_reporting_and_delete(clients):
    alice, bob, stranger = clients
    a = enroll(alice, 'alice@epita.fr', 'EPITA', 'Alice', gender='Femme')
    b = enroll(bob, 'bob@supbiotech.fr', 'SupBiotech', 'Bob', gender='Homme')
    c = enroll(stranger, 'camille@epita.fr', 'EPITA', 'Camille', gender='Non-binaire')
    assert alice.patch('/api/me',json={'interests':['Programmation','Randonnée']}).status_code==200
    assert bob.patch('/api/me',json={'interests':['Programmation','Photographie']}).status_code==200
    profiles = alice.get('/api/discover').json()['profiles']
    assert b['id'] in [p['id'] for p in profiles]
    assert alice.post('/api/swipes',json={'target_id':b['id'],'action':'like'}).json()['matched'] is False
    assert b['id'] not in [p['id'] for p in alice.get('/api/discover').json()['profiles']]
    assert a['id'] in [p['id'] for p in bob.get('/api/likes-received').json()['profiles']]
    swap = bob.post('/api/swipes',json={'target_id':a['id'],'action':'like'}).json()
    assert swap['matched'] is True
    match_id = swap['match_id']
    assert len(alice.get('/api/matches').json()['matches'])==1
    assert stranger.get(f'/api/matches/{match_id}/messages').status_code==404
    sent=alice.post(f'/api/matches/{match_id}/messages',json={'body':'Bonjour !'})
    assert sent.status_code==200, sent.text
    assert bob.get(f'/api/matches/{match_id}/messages').json()['messages'][0]['body']=='Bonjour !'
    assert stranger.post('/api/reports',json={'target_id':a['id'],'reason':'Propos irrespectueux'}).status_code==200
    assert bob.post('/api/blocks',json={'target_id':a['id']}).status_code==200
    assert alice.get('/api/matches').json()['matches']==[]
    assert alice.get(f'/api/matches/{match_id}/messages').status_code==404
    assert bob.post('/api/swipes',json={'target_id':a['id'],'action':'like'}).status_code==404
    assert alice.get('/api/account/export').status_code==200
    assert alice.delete('/api/account').status_code==200
    assert alice.get('/api/me').status_code==401
    assert bob.get('/api/matches').json()['matches']==[]

def test_filters_and_validation(clients):
    alice,bob,_=clients
    a=enroll(alice,'ff@epita.fr','EPITA','Françoise',gender='Femme')
    b=enroll(bob,'mm@supbiotech.fr','SupBiotech','Martin',gender='Homme')
    bad={'schools':['EPITA'], 'genders':['Femme'], 'age_min':27,'age_max':22,'city':'Toutes'}
    assert alice.put('/api/me/preferences',json=bad).status_code==422
    good={**bad,'age_min':18,'age_max':40}
    assert alice.put('/api/me/preferences',json=good).status_code==200
    assert b['id'] not in [p['id'] for p in alice.get('/api/discover').json()['profiles']]
    assert alice.patch('/api/me',json={'interests':['a']*13}).status_code==422
    assert len(alice.get('/api/interests').json()['families'])==40
    assert alice.get('/api/health').status_code==200
    assert alice.get('/').status_code==200

def test_photo_private_until_moderated_and_static_files_protected(clients):
    from io import BytesIO
    from PIL import Image
    from sqlalchemy import select
    from backend.main import Photo
    alice,bob,_ = clients
    a = enroll(alice, 'photo@epita.fr', 'EPITA', 'Robin')
    b = enroll(bob, 'reader@supbiotech.fr', 'SupBiotech', 'Marine')
    src = BytesIO()
    Image.new('RGB',(32,32),(120,130,150)).save(src,format='PNG')
    up = alice.post('/api/me/photos', files={'photo':('test.png',src.getvalue(),'image/png')})
    assert up.status_code==200,up.text
    photo_id = up.json()['id']
    assert up.json()['status']=='pending'
    assert alice.get(f'/api/photos/{photo_id}').status_code==200
    assert bob.get(f'/api/photos/{photo_id}').status_code==404
    assert not bob.get('/api/discover').json()['profiles'][0]['photos']
    with alice.app.state.local_session() as session:
        photo=session.get(Photo,photo_id)
        photo.status='approved'
        session.commit()
    # Jeudi rule: even approved photos stay private until the two people have matched.
    assert bob.get(f'/api/photos/{photo_id}').status_code==404
    alice.post('/api/swipes',json={'target_id':b['id'],'action':'like'})
    assert bob.post('/api/swipes',json={'target_id':a['id'],'action':'like'}).json()['matched'] is True
    assert bob.get(f'/api/photos/{photo_id}').status_code==200
    assert alice.patch('/api/me',json={'visible':False}).status_code==200
    assert bob.get(f'/api/photos/{photo_id}').status_code==404
    assert alice.delete(f'/api/me/photos/{photo_id}').status_code==200
    assert alice.get(f'/api/photos/{photo_id}').status_code==404
    # Internal application code and database must never be available as static assets.
    for path in ['/backend/main.py','/.env.example','/requirements.txt','/campus.db','/private_uploads/test.webp']:
        assert alice.get(path).status_code==404,path

def test_websocket_requires_match_and_same_origin(clients):
    from starlette.websockets import WebSocketDisconnect
    alice,bob,stranger=clients
    a=enroll(alice,'websocket@epita.fr','EPITA','Éloïse')
    b=enroll(bob,'websocket@supbiotech.fr','SupBiotech','Eden')
    enroll(stranger,'outsider@epita.fr','EPITA','Solène')
    alice.post('/api/swipes',json={'target_id':b['id'],'action':'like'})
    match=bob.post('/api/swipes',json={'target_id':a['id'],'action':'like'}).json()['match_id']
    with alice.websocket_connect(f'/api/ws/matches/{match}',headers={'origin':'http://testserver'}) as ws:
        ws.send_text('ping')
        assert ws.receive_json()=={'type':'pong'}
    with pytest.raises(WebSocketDisconnect):
        with stranger.websocket_connect(f'/api/ws/matches/{match}',headers={'origin':'http://testserver'}) as ws:
            ws.receive_json()
    with pytest.raises(WebSocketDisconnect):
        with alice.websocket_connect(f'/api/ws/matches/{match}',headers={'origin':'https://evil.example'}) as ws:
            ws.receive_json()

def test_csrf_protection_and_security_headers(clients):
    alice, _, _ = clients
    r = alice.get('/')
    assert r.status_code == 200
    assert "script-src 'self'" in r.headers['content-security-policy']
    assert r.headers['x-frame-options'] == 'DENY'
    # A forged origin cannot make a state-changing request.
    bad = alice.post('/api/auth/request-code',
                     json={'email':'foo@epita.fr','school':'EPITA'},
                     headers={'Origin':'https://malicious.example'})
    assert bad.status_code == 403
    missing_header = alice.post('/api/auth/request-code',
                     json={'email':'bar@epita.fr','school':'EPITA'},
                     headers={'X-Campus-Request':''})
    assert missing_header.status_code == 403


def test_photo_order_moderator_and_pending_accounts(tmp_path, monkeypatch):
    from backend.main import Photo
    from io import BytesIO
    from PIL import Image
    from fastapi.testclient import TestClient
    monkeypatch.setenv('REQUIRE_ACCOUNT_APPROVAL','true')
    monkeypatch.setenv('ADMIN_EMAILS','admin@epita.fr')
    app = create_app(f"sqlite:///{tmp_path / 'mod.db'}", dev_otp=True)
    headers={'X-Campus-Request':'1'}
    with TestClient(app, headers=headers) as admin, TestClient(app,headers=headers) as person:
        a=enroll(admin,'admin@epita.fr','EPITA','Admin')
        u=enroll(person,'student@supbiotech.fr','SupBiotech','Student')
        me=person.get('/api/me').json()
        assert me['pending_approval'] is True
        assert person.get('/api/discover').status_code == 403
        queue=admin.get('/api/admin/queue').json()
        assert u['id'] in [x['id'] for x in queue['accounts']]
        assert admin.patch(f"/api/admin/accounts/{u['id']}",json={'approved':True}).status_code == 200
        assert person.get('/api/discover').status_code == 200
        source=BytesIO()
        Image.new('RGB',(48,64),(22,33,99)).save(source,format='PNG')
        ids=[]
        for n in range(2):
            x=person.post('/api/me/photos', files={'photo':(f'p{n}.png',source.getvalue(),'image/png')})
            assert x.status_code == 200, x.text
            ids.append(x.json()['id'])
        assert person.get('/api/me').json()['photos'][0]['id'] == ids[0]
        assert person.patch('/api/me/photos/order',json={'photo_ids':list(reversed(ids))}).status_code == 200
        assert person.get('/api/me').json()['photos'][0]['id'] == ids[1]
        assert admin.get('/api/admin/photos/'+ids[0]).status_code == 200
        assert admin.patch('/api/admin/photos/'+ids[0],json={'status':'approved'}).status_code == 200
        assert admin.patch('/api/admin/photos/'+ids[1],json={'status':'rejected'}).status_code == 200
        assert person.get('/api/me').json()['photos'][0]['id'] == ids[0]
        assert person.get('/api/me').json()['photos'][0]['status'] == 'approved'
        assert person.get('/api/admin/queue').status_code == 403
