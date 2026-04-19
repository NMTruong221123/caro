# Game Co Caro Da Che Do

Du an web game co caro voi:
- Frontend: HTML/CSS/JavaScript thuan
- Backend: Python Flask
- Game logic: Python
- Database: SQLite (luu truc tiep vao file)

## Tinh nang

1. Che do choi voi may (AI)
- Quan co X/O truyen thong
- AI Minimax + alpha-beta pruning
- 3 do kho: easy, medium, hard

2. Che do nhieu nguoi
- 2-4 nguoi choi
- Quan co la hinh khoi co mau: vuong, tam giac, chu nhat, tron

3. Phong online realtime (WebSocket)
- Tao phong / vao phong theo ma phong
- Nguoi choi that, dong bo ban co theo thoi gian thuc
- Server kiem soat luot choi dung nguoi dung
- Chi chu phong moi duoc bat dau tran
- Co chat trong phong qua Socket.IO
- Chu phong co the set/bo co-host
- Chu phong va co-host co the mute/unmute va kick thanh vien
- Kick khi dang choi se tinh thua ky thuat cho nguoi bi kick
- Chat co loc tu cam va gioi han spam

4. Tai khoan + bang xep hang
- Dang ky / dang nhap
- Luu ELO chuan theo rating doi thu (expected score)
- K-factor dong theo so tran da choi (nguoi moi bien dong nhanh hon, nguoi choi lau on dinh hon)
- Tai khoan moi mac dinh rank Dong V (V thap nhat, I cao nhat trong cung bac)

5. Luu tran dau
- Luu tran dau, trang thai, nuoc di vao SQLite

## Cau truc chinh

- frontend/: giao dien va tuong tac
- backend/: Flask API
- game/: luat choi, AI, shape token
- database/: schema SQLite va script khoi tao

## Chay du an

1. Tao moi truong ao (khuyen nghi)

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Cai thu vien

```powershell
pip install -r requirements.txt
```

3. Khoi tao database (co the bo qua vi server tu tao neu chua co)

```powershell
python database/init_db.py
```

4. Chay server

```powershell
python backend/server.py
```

5. Mo trinh duyet

- Truy cap http://127.0.0.1:5000

## API chinh

- POST /api/game/start
- POST /api/game/move
- GET /api/game/state/<match_id>
- POST /api/user/register
- POST /api/user/login
- GET /api/user/me
- GET /api/user/leaderboard
- POST /api/online/room/create
- POST /api/online/room/join
- GET /api/online/room/<code>

## Su dung phong online

1. Dang ky va dang nhap o panel ben trai
2. Chon che do "Phong online realtime"
3. Tao phong hoac nhap ma phong de vao phong
4. Bam "Bat dau online" de tao tran khi da du nguoi
5. Choi tren cung ma phong o cac tab/thiet bi khac nhau
