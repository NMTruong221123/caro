# Co Caro - Fullstack Web Game

Du an game Co Caro fullstack, co cac che do choi voi may, local multiplayer, phong online realtime va rank 1v1.

## Live Demo

- Web live: https://caro-0th9.onrender.com
- Repository: https://github.com/NMTruong221123/caro

## Tech Stack

- Frontend: HTML, CSS, JavaScript (module)
- Backend: Python Flask + Flask-SocketIO
- Game engine: Python
- Database: SQLite
- Deployment: Render (Docker)

## Tinh nang chinh

### 1) Gameplay

- AI mode (easy, medium, hard)
- Local multiplayer 2-4 nguoi
- Online room realtime qua Socket.IO
- Ranked queue 1v1
- Ban co mo rong dong:
	- Khoi dau 15x15
	- Khi danh sat bien, ban co tu mo rong theo cum 15 o moi phia
- Zoom board:
	- Zoom in / Zoom out trong cac trang choi

### 2) Tai khoan va rank

- Dang ky, dang nhap, session token
- ELO update theo doi thu
- He thong rank tier + stars
- Leaderboard cho AI / Room / Rank
- Mailbox + inventory + equip title/frame

### 3) Online moderation

- Chu phong / co-host
- Mute / unmute / kick
- Chuyen chu phong
- Chat filter va spam guard
- Anti-abuse cho rank queue (rate limit theo user/IP)

### 4) Trai nghiem tran dau

- Popup thong bao ket qua tran (thang/hoa)
- Nut quay ve trang chon che do
- Match history + replay
- Reconnect vao tran dang choi

### 5) Admin

- Tai khoan built-in:
	- Username: ADMIN
	- Password: 123456
- Dashboard mini: thong ke room, event bao mat, runtime errors, chat filter

## Cau truc thu muc

- frontend/: giao dien web
- backend/: API Flask, Socket.IO, controllers/services
- game/: logic game, AI, shape/token
- database/: schema va script init
- tests/: test suite

## Chay local

### 1) Tao virtual environment

PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2) Cai dependencies

```powershell
pip install -r requirements.txt
```

### 3) Khoi tao DB (tuy chon)

```powershell
python database/init_db.py
```

### 4) Chay server

```powershell
python backend/server.py
```

### 5) Mo trinh duyet

- http://127.0.0.1:5000

## Test

```powershell
python -m pytest -q
```

## Deploy Render (khong can the)

Repo da co san file render.yaml va Dockerfile.

1. Vao Render dashboard
2. New + > Blueprint
3. Chon repo NMTruong221123/caro
4. Deploy

Luu y goi free:

- Service co the sleep khi khong co truy cap
- Request dau tien sau khi sleep co the tre

## API tieu bieu

- POST /api/game/start
- POST /api/game/move
- GET /api/game/state/<match_id>
- POST /api/user/register
- POST /api/user/login
- GET /api/user/me
- GET /api/user/leaderboard
- GET /api/user/matches
- GET /api/user/matches/<match_id>/replay
- POST /api/online/room/create
- POST /api/online/room/join
- GET /api/online/room/active

## Ghi chu van hanh

- Neu cap nhat frontend nhung chua thay doi ngay, hay Ctrl+F5 de clear cache.
- Render free co cold start, la hanh vi binh thuong.
