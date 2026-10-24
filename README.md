# AWS EC2 Self-Service Provisioning Portal

A web portal where users request a cloud server (an AWS EC2 instance), an admin approves it, and the portal creates it automatically on real AWS using Terraform. The user can then track its status, see the public IP, and destroy it, or it is destroyed automatically when the chosen time ends.

## 1. About the project

**The problem:** In many teams and colleges, getting a cloud server means asking an admin, who then logs in to AWS and creates it by hand. This is slow, error-prone, and nobody tracks cost or security.

**The solution:** A self-service portal with an approval workflow.

1. A **user** fills a request form (purpose, workload type, storage, how long they need it).
2. The portal **recommends** an instance type, shows an **estimated cost** and a **security score**.
3. An **admin** reviews the request and approves or rejects it (a rejection needs a reason).
4. On approval, the backend runs **Terraform** and creates the EC2 instance in AWS (region `ap-south-1`, Mumbai).
5. The user sees the status and the public IP. When the time is over, the instance is **auto-destroyed** to save money.

### Features

- User registration and login (JWT)
- Roles: `user` and `admin`
- Request form with live recommendation, cost estimate and security check
- Admin approve / reject with preset reasons
- Automatic provisioning and destroy with Terraform
- Status tracking: `pending` → `approved` → `provisioning` → `provisioned` → `destroyed` (also `rejected`, `failed` with retry)
- Auto-destroy scheduler (checks every 60 seconds)
- Protection: one Terraform job per request, lock timeout, cleanup after failure, recovery of stuck jobs on startup
- Responsive UI (desktop, tablet, mobile)
- Docker support

### Technology

| Part | Technology |
|---|---|
| Frontend | React + Vite |
| Backend | FastAPI, SQLAlchemy, Pydantic |
| Database | SQLite |
| Infrastructure | Terraform, AWS EC2 |
| Packaging | Docker, Docker Compose, Nginx |

### Workload to instance mapping

| Workload | Instance type | Memory |
|---|---|---|
| Low | `t3.micro` | 1 GiB |
| Medium | `t3.small` | 2 GiB |
| High | `c7i-flex.large` | 4 GiB (2 vCPU) |

`t3.medium` is not used because the AWS Free plan refuses it. Storage can be 8 to 30 GB. Duration options: 2 hours, 6 hours, 1 day, 3 days, 7 days, or a custom end date (maximum 90 days).

## 2. Requirements

You need:

| Requirement | Why |
|---|---|
| An **AWS account** | Instances are created for real |
| An **IAM user with access keys** | The portal uses it to create EC2 |
| **Git** | To get the code |
| **Docker Desktop** (Docker way) | Easiest way to run |
| **Python 3.12 or newer**, **Node.js 20 or newer**, **Terraform 1.5 or newer**, **AWS CLI** (terminal way) | Only if you do not use Docker |

Use either the Docker way or the terminal way, not both at once (they use the same ports).

### Cost warning

Real instances cost real money (or AWS credits). Test with the **2 hours** option and always destroy instances you no longer need. Prices shown in the portal are estimates only, check the AWS pricing page for exact values.

## 3. AWS setup (one time)

1. Log in to the AWS Console and open **IAM → Users → Create user**.
2. Give it permission to manage EC2 (for a demo, `AmazonEC2FullAccess` is enough).
3. Open the user → **Security credentials → Create access key**. Copy the **Access key ID** and **Secret access key**.
4. Never put these keys in Git, screenshots or the README.

## 4. Get the code

```powershell
git clone https://github.com/Prathamesh13-n/PBL-Sem-V.git
cd PBL-Sem-V
```

## 5. Option A: run with Docker (recommended)

1. Create a file named `.env` in the project root:

```
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_DEFAULT_REGION=ap-south-1
DATABASE_URL=sqlite:////data/portal.db
SECRET_KEY=put-a-long-random-text-here
AUTO_PROVISION=1
```

Optional, for testing only: add `FORCE_LIFETIME_HOURS=2` to make every server expire and be destroyed after 2 hours, whatever duration the user chose. Remove it for normal use.

2. Start everything:

```powershell
docker compose up -d --build
```

3. Create the database tables (first time only):

```powershell
docker compose exec backend python /app/backend/init_db.py
```

4. Open the app:

- Website: http://localhost:5173
- API docs: http://localhost:8000/docs

Useful commands:

```powershell
docker compose logs -f backend     # see logs
docker compose down                # stop
docker compose up -d --build       # rebuild after changing code
```

After any code change you must rebuild with `--build`, because the image holds a copy of the files.

## 6. Option B: run from the terminal

### Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
aws configure          # enter your keys, region ap-south-1
```

Create `backend\.env`:

```
DATABASE_URL=sqlite:///./portal.db
SECRET_KEY=put-a-long-random-text-here
```

Do not add other names to `backend\.env`: the backend refuses unknown settings in that file. Optional testing safety (terminal only, in the same window before `uvicorn`):

```powershell
$env:FORCE_LIFETIME_HOURS = "2"
```

With it, every server is destroyed automatically after 2 hours.

Create the tables and start the server:

```powershell
python init_db.py
uvicorn app.main:app --reload
```

### Frontend (second terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## 7. Create the first admin

1. Open the website and **register** a normal account.
2. Make it an admin:

```powershell
# terminal way (venv active, inside backend)
python make_admin.py you@example.com

# Docker way
docker compose exec backend python /app/backend/make_admin.py you@example.com
```

3. Log out and log in again. You now see the admin pages.

## 8. How to use

**As a user**

1. Register and log in.
2. Click **New request** and fill the 5 sections: basic details, duration, workload, configuration, review.
3. Check the recommended instance, estimated cost and security score, then submit.
4. Watch the request status on the dashboard. When it is `provisioned` you see the public IP.
5. Click destroy when finished, or wait for auto-destroy.

**As an admin**

1. Open a pending request and read the review summary and security check.
2. Approve (the instance is created automatically) or reject with a reason.
3. For risky or costly requests the portal asks you to confirm.

## 9. Security checks

Each request gets a score out of 100 (85 and above low risk, 60 to 84 medium, below 60 high). Checks include public access, SSH closed, risky ports, IAM instance profile, disk encryption, IMDSv2, long duration and missing purpose. Instances are created with an encrypted disk and IMDSv2 required.

## 10. Helper scripts (inside `backend`)

| Command | What it does |
|---|---|
| `python init_db.py` | Create database tables |
| `python make_admin.py email` | Make a user admin |
| `python destroy_all.py` | List running instances |
| `python destroy_all.py --yes` | Destroy all running instances |
| `python reset_demo.py` | Dry run of clearing requests |
| `python reset_demo.py --yes` | Clear all requests (refuses while instances run) |

Before you finish a demo or testing session, run `destroy_all.py` and also check the EC2 page in the AWS Console.

## 11. Project structure

```
PBL-Sem-V/
├── backend/            FastAPI app (app/), helper scripts, Dockerfile
├── frontend/           React + Vite app, nginx.conf, Dockerfile
├── terraform/          main.tf and variables.tf used for every request
├── docker-compose.yml
├── .env                your secrets (never commit)
└── README.md
```

Runtime folders `terraform_runs/` and `.terraform-plugin-cache/` are created automatically.

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| `no such table` | Run `init_db.py` (see sections 5 and 6) |
| Backend fails with missing settings | `DATABASE_URL` and `SECRET_KEY` must be in `.env` |
| `No module named sqlalchemy` | Activate the venv first |
| Port already in use | You are running Docker and terminal together; stop one |
| Request `failed` with "not eligible for Free Tier" | The instance type is not allowed on your AWS plan; use a smaller workload |
| `failed` request | Open it and click retry; check backend logs for the Terraform error |
| Changes not showing in Docker | `docker compose up -d --build` |
| `VcpuLimitExceeded` error on a request | The AWS account allows 8 vCPUs at once (4 servers). Destroy running servers (`python destroy_all.py --yes`), then click Retry |
| `Extra inputs are not permitted` when starting | An unknown name is in `backend\.env`. Keep only `DATABASE_URL` and `SECRET_KEY` there |
| Login works but no admin pages | Run `make_admin.py`, then log in again |

## 13. Limitations

- SQLite and a single backend process, suitable for demos and small teams, not large production.
- Only EC2 in one region (`ap-south-1`).
- The AWS account vCPU quota (8 vCPUs) allows at most 4 servers to run at the same time; users can still send unlimited requests.
- Cost values are estimates, not a bill.
- Recommendation, cost and security checks are rule-based, not machine learning.

## 14. Safety notes

- Keep `.env` out of Git (add it to `.gitignore`).
- Use a dedicated IAM user with only the permissions it needs, and delete its keys when the project is over.
- Rotate any key that was ever shown or committed by mistake.
