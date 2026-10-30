# AWS EC2 Self-Service Provisioning Portal

A web portal where users request a cloud server (an AWS EC2 instance), an administrator approves it, and the portal creates it automatically on real AWS with Terraform. The user then tracks its status and public IP, and the server is destroyed automatically when the chosen time ends.

> **Cost warning:** this project creates **real servers on a real AWS account**. They cost money (or AWS credits) while they run. Read section 12 before you test.

---

## Table of contents

1. [What this project does](#1-what-this-project-does)
2. [Features](#2-features)
3. [How it works](#3-how-it-works)
4. [Technology](#4-technology)
5. [Requirements](#5-requirements)
6. [AWS setup (one time)](#6-aws-setup-one-time)
7. [Get the code](#7-get-the-code)
8. [Configuration reference](#8-configuration-reference)
9. [Run option A: Docker](#9-run-option-a-docker-recommended)
10. [Run option B: terminal (no Docker)](#10-run-option-b-terminal-no-docker)
11. [First use: create users and the admin](#11-first-use-create-users-and-the-admin)
12. [Cost safety: read before testing](#12-cost-safety-read-before-testing)
13. [How to use the portal](#13-how-to-use-the-portal)
14. [Rules and limits](#14-rules-and-limits)
15. [Security checks](#15-security-checks)
16. [API reference](#16-api-reference)
17. [Helper scripts](#17-helper-scripts)
18. [Project structure](#18-project-structure)
19. [Testing checklist](#19-testing-checklist)
20. [Troubleshooting](#20-troubleshooting)
21. [Limitations](#21-limitations)
22. [Future scope](#22-future-scope)
23. [Security notes](#23-security-notes)

---

## 1. What this project does

**The problem.** In colleges and small teams, getting a cloud server means asking an admin, who logs in to AWS and builds it by hand. This is slow and error-prone, and nobody tracks cost, security or who asked for what.

**The solution.** A self-service portal with an approval workflow:

1. A **user** fills in a request: purpose, workload type, storage and how long they need the server.
2. The portal **recommends** an instance type, shows an **estimated cost** and a **security score**.
3. An **admin** reviews the request and approves it, or rejects it with a reason.
4. On approval the backend runs **Terraform** and creates the EC2 instance in AWS (region `ap-south-1`, Mumbai).
5. The user sees the status and the public IP. When the time is over, the server is **destroyed automatically**.

## 2. Features

- User registration and login (JWT tokens)
- Two roles: `user` and `admin`
- Request form in 5 steps with a live recommendation, cost estimate and security check
- Admin approve or reject, with preset rejection reasons and a note
- Automatic provisioning and destruction with Terraform
- Status tracking for every request (see section 3)
- Auto-destroy scheduler that checks every 60 seconds
- Failure handling: failed requests keep the error, partial resources are cleaned up, retry is available
- Protection against double jobs (HTTP 409), Terraform timeouts, and recovery of stuck jobs at startup
- Responsive interface for desktop, tablet and mobile
- Docker and Docker Compose support

## 3. How it works

```
 User (browser)                Admin (browser)
      |                              |
      v                              v
 React + Vite frontend  ---->  FastAPI backend  ---->  SQLite database
                                     |
                                     v
                        Terraform (one folder per request)
                                     |
                                     v
                         AWS EC2 (ap-south-1, Mumbai)
```

### Request status lifecycle

```
pending --> approved --> provisioning --> provisioned --> destroyed
   |                          |
   v                          v
rejected                   failed --(retry)--> provisioning
```

| Status | Meaning |
|---|---|
| `pending` | Waiting for the admin |
| `rejected` | Admin said no, with a reason |
| `approved` | Admin said yes (provisioning starts automatically unless `AUTO_PROVISION=0`) |
| `provisioning` | Terraform is creating the server |
| `provisioned` | The server is running and the public IP is shown |
| `failed` | AWS or Terraform returned an error (shown on the request page). Click Retry |
| `destroyed` | The server was removed, by the user, the admin or the auto-destroy scheduler |

## 4. Technology

| Part | Technology |
|---|---|
| Frontend | React + Vite |
| Backend | Python, FastAPI, SQLAlchemy, Pydantic |
| Database | SQLite |
| Infrastructure as Code | Terraform (AWS provider 5.x) |
| Cloud | AWS EC2, region `ap-south-1` |
| Packaging | Docker, Docker Compose, Nginx |

## 5. Requirements

| Requirement | Needed for |
|---|---|
| An **AWS account** and an **IAM user with access keys** | Creating the servers |
| **Git** | Getting the code |
| **Docker Desktop** | Docker way (easiest) |
| **Python 3.12 or newer** (tested on 3.14) | Terminal way |
| **Node.js 20 or newer** and npm | Terminal way |
| **Terraform 1.5 or newer** (on your `PATH`) | Terminal way |
| **AWS CLI** | Terminal way (`aws configure`) |

Use **either** Docker **or** the terminal, not both at the same time. They use the same ports (8000 and 5173).

## 6. AWS setup (one time)

1. Sign in to the AWS Console and open **IAM → Users → Create user**.
2. Attach the policy **`AmazonEC2FullAccess`**. (For a stricter setup, allow only the EC2 actions that Terraform needs.)
3. Open the user → **Security credentials → Create access key**. Choose "Command Line Interface".
4. Copy the **Access key ID** and the **Secret access key**. You see the secret only once.
5. Make sure your account can launch the instance types the portal uses (see section 14). New accounts on the AWS Free plan only allow some types, and have a **vCPU limit of 8**.

Never put these keys in Git, in screenshots, or in this README.

## 7. Get the code

```powershell
git clone https://github.com/Prathamesh13-n/PBL-Sem-V.git
cd PBL-Sem-V
```

## 8. Configuration reference

### 8.1 Settings files

| File | Used by | Contents |
|---|---|---|
| `.env` in the **project root** | Docker | AWS keys, database path, secret key, options |
| `backend\.env` | Terminal way | `DATABASE_URL` and `SECRET_KEY` only |
| `aws configure` (AWS CLI) | Terminal way | AWS keys and region |

`.env` files are listed in `.gitignore`, so Git never uploads them.

### 8.2 Variables

| Variable | Where | Required | Meaning |
|---|---|---|---|
| `AWS_ACCESS_KEY_ID` | root `.env` (Docker) | Docker: yes | IAM access key ID |
| `AWS_SECRET_ACCESS_KEY` | root `.env` (Docker) | Docker: yes | IAM secret access key |
| `AWS_DEFAULT_REGION` | root `.env` (Docker) | Docker: yes | Use `ap-south-1` |
| `DATABASE_URL` | both | yes | Docker: `sqlite:////data/portal.db`. Terminal: `sqlite:///./portal.db` |
| `SECRET_KEY` | both | yes | Long random text used to sign login tokens |
| `AUTO_PROVISION` | environment | no, default `1` | `1` = approving starts provisioning at once. `0` = approve, then click Provision |
| `TERRAFORM_INIT_TIMEOUT` | environment | no, default 600 | Seconds allowed for `terraform init` |
| `TERRAFORM_APPLY_TIMEOUT` | environment | no, default 900 | Seconds allowed for `terraform apply` |
| `TERRAFORM_DESTROY_TIMEOUT` | environment | no, default 900 | Seconds allowed for `terraform destroy` |
| `FORCE_LIFETIME_HOURS` | environment | no | **Testing safety.** Makes every server expire after this many hours, whatever the user chose (for example `2`). Remove it for the real demo |

> **Important:** the backend refuses unknown names inside `backend\.env`. Put only `DATABASE_URL` and `SECRET_KEY` there. Set the optional variables as real environment variables (for example `$env:FORCE_LIFETIME_HOURS = "2"` in the same PowerShell window, before `uvicorn`), or in the root `.env` for Docker.

### 8.3 Generate a secret key

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the result as `SECRET_KEY`.

## 9. Run option A: Docker (recommended)

1. Create `.env` in the project root:

```
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_DEFAULT_REGION=ap-south-1
DATABASE_URL=sqlite:////data/portal.db
SECRET_KEY=put-a-long-random-text-here
AUTO_PROVISION=1
```

2. Build and start (first time takes a few minutes):

```powershell
docker compose up -d --build
```

3. Create the database tables (first time only):

```powershell
docker compose exec backend python /app/backend/init_db.py
```

4. Open the portal:

| What | Address |
|---|---|
| Website | http://localhost:5173 |
| API documentation (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

Useful commands:

```powershell
docker compose ps                  # what is running
docker compose logs -f backend     # live backend logs
docker compose down                # stop (data is kept in volumes)
docker compose up -d --build       # rebuild after you change the code
```

Docker keeps three volumes: the database, the Terraform run folders, and the Terraform plugin cache. The image holds a **copy** of the code, so after any change you must rebuild with `--build`.

## 10. Run option B: terminal (no Docker)

### Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
aws configure              # enter your keys, region ap-south-1
```

If PowerShell blocks the activate script, run this once in that window:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Create `backend\.env` with exactly these two lines:

```
DATABASE_URL=sqlite:///./portal.db
SECRET_KEY=put-a-long-random-text-here
```

Create the tables and start the server:

```powershell
python init_db.py
uvicorn app.main:app --reload
```

The backend runs on http://localhost:8000.

### Frontend (a second terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

Check that Terraform is installed: `terraform -version`.

## 11. First use: create users and the admin

There is no default admin. Create one like this:

1. Open the website and **register** an account, for example `admin@example.com`.
2. Make it an admin (run in the `backend` folder, with the venv active):

```powershell
python make_admin.py admin@example.com
```

Docker way:

```powershell
docker compose exec backend python /app/backend/make_admin.py admin@example.com
```

3. **Log out and log in again.** The account now sees the admin pages.

Register a second account for a normal user. For testing, use two browsers (or one normal and one private window), so you can be the user and the admin at the same time.

## 12. Cost safety: read before testing

- **Test with the 2-hour duration** and the smallest sizes.
- **Destroy every server** as soon as you have checked it (Destroy button, or `python destroy_all.py --yes`).
- For tests, set `FORCE_LIFETIME_HOURS=2` so nothing can live longer than 2 hours by accident.
- After each session, open **AWS Console → EC2 → Instances** in the **Mumbai (ap-south-1)** region and confirm that every row says **Terminated**. Also check **Volumes**: it should be empty.
- The cost shown in the portal is an **estimate**. The real bill is on the AWS billing page.
- Never approve long requests (3 days, 7 days, 90 days) while testing.

## 13. How to use the portal

### As a user

1. Register and log in.
2. Click **New request** and fill in the five sections:
   1. Basic details (name and purpose)
   2. Duration
   3. Workload and recommendation
   4. Configuration (storage)
   5. Review and submit
3. Check the recommended instance, the estimated cost and the security score, then submit. The status is **pending**.
4. Watch the dashboard. When the status is **provisioned**, the public IP appears on the request page.
5. Click **Destroy** when you are done, or wait for the auto-destroy.
6. If the request is **rejected**, the reason is shown, and you can submit a new request.

### As an admin

1. Log in and open the **Admin** dashboard. It lists all requests.
2. Open a request and read the review summary, the cost and the security check.
3. **Approve** it. The portal starts provisioning automatically. For risky or costly requests it asks you to confirm.
4. Or **reject** it: choose a preset reason and add a note (5 to 300 characters).
5. If a request is **failed**, read the error and click **Retry Provisioning** after you fix the cause.

## 14. Rules and limits

### Workload to instance type

| Workload | Instance type | vCPU | Memory |
|---|---|---|---|
| Low | `t3.micro` | 2 | 1 GiB |
| Medium | `t3.small` | 2 | 2 GiB |
| High | `c7i-flex.large` | 2 | 4 GiB |

`t3.medium` is not used, because the AWS Free plan refuses it ("not eligible for Free Tier"). Older requests that used `t3.medium` are mapped to `c7i-flex.large`. Allowed types in the Terraform template: `t2.micro`, `t3.micro`, `t3.small`, `c7i-flex.large`.

### Request limits

| Item | Limit |
|---|---|
| Storage | 8 to 30 GB |
| Quick duration options | 2 hours, 6 hours, 1 day, 3 days, 7 days |
| Custom end date | up to 90 days |
| Rejection reason | 5 to 300 characters |

### Estimated cost (8 GB storage, USD)

The estimate adds the instance price, the storage price (gp3, prorated by hours) and the public IPv4 address price. Prices are on-demand estimates for `ap-south-1`: `t3.micro` 0.0112, `t3.small` 0.0224, `c7i-flex.large` 0.0848 USD per hour, storage 0.0912 USD per GB-month, public IPv4 0.005 USD per hour, 88 INR per USD. **Check them against the AWS pricing page** and edit `backend/app/pricing.py` if they change.

| Duration | t3.micro | t3.small | c7i-flex.large |
|---|---|---|---|
| 2 hours | 0.03 | 0.06 | 0.18 |
| 6 hours | 0.10 | 0.17 | 0.54 |
| 1 day | 0.41 | 0.68 | 2.18 |
| 7 days | 2.89 | 4.77 | 15.25 |
| 30 days | 12.38 | 20.45 | 65.38 |
| 90 days | 37.15 | 61.34 | 196.13 |

### Capacity: only 4 servers at the same time

A new AWS account allows **8 vCPUs** running at once. Each type above uses 2 vCPUs, so **at most 4 servers can run together**. Users can send unlimited requests, but the 5th approved request **fails** with `VcpuLimitExceeded` until a running server is destroyed or expires. Then click **Retry Provisioning**. You can ask AWS for a higher limit at https://aws.amazon.com/contact-us/ec2-request.

## 15. Security checks

Each request gets a score from 0 to 100. Points are taken off for risky findings. **85 or more = Low risk, 60 to 84 = Medium, below 60 = High.**

| Check | What it looks at |
|---|---|
| Public access | Port 80 open to the internet (warning, 5 points) |
| SSH | SSH (port 22) is closed |
| Risky ports | No dangerous ports are open |
| IAM profile | No IAM instance profile is attached |
| Disk encryption | Root disk is encrypted |
| IMDSv2 | The instance metadata service requires tokens |
| Long duration | More than 7 days (warning, 10 points) |
| Missing purpose | The request has no purpose (warning, 5 points) |

Encryption and IMDSv2 are written into `terraform/main.tf`, so every server gets them.

## 16. API reference

Open **http://localhost:8000/docs** for the full interactive documentation (including register and login). Main request endpoints (all need a login token):

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/requests` | user | Create a request |
| GET | `/requests` | user / admin | List requests (users see their own) |
| GET | `/requests/preview` | user | Recommendation, cost and security for given inputs |
| GET | `/requests/recommendation` | user | Recommended instance for a workload |
| GET | `/requests/estimate` | user | Cost estimate |
| GET | `/requests/duration-options` | user | Duration choices with prices |
| GET | `/requests/{id}` | owner / admin | One request |
| GET | `/requests/{id}/security` | owner / admin | Security check of a request |
| GET | `/requests/{id}/deployment` | owner / admin | Instance ID, IP and expiry time |
| PATCH | `/requests/{id}/approve` | admin | Approve |
| PATCH | `/requests/{id}/reject` | admin | Reject with a reason |
| PATCH | `/requests/{id}/start-provisioning` | admin | Provision (or retry) |
| POST | `/requests/{id}/destroy` | owner / admin | Destroy the server |

## 17. Helper scripts

Run these in the `backend` folder with the venv active (Docker: `docker compose exec backend python /app/backend/<script>`).

| Command | What it does |
|---|---|
| `python init_db.py` | Create the database tables (safe to run again) |
| `python make_admin.py email` | Make a registered user an admin |
| `python destroy_all.py` | List the servers that are still running |
| `python destroy_all.py --yes` | Destroy all running servers |
| `python reset_demo.py` | Dry run: show which requests would be cleared |
| `python reset_demo.py --yes` | Clear all requests (refuses while servers run; users are kept) |

## 18. Project structure

```
PBL-Sem-V/
├── backend/
│   ├── app/                 FastAPI code (routes, models, security, pricing,
│   │                        recommendation, terraform_runner)
│   ├── init_db.py           create tables
│   ├── make_admin.py        promote a user to admin
│   ├── destroy_all.py       destroy running servers
│   ├── reset_demo.py        clear test requests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/                 React pages and components
│   ├── nginx.conf
│   └── Dockerfile
├── terraform/               main.tf, variables.tf, outputs.tf (used for every request)
├── docker-compose.yml
├── .env                     your secrets (never commit)
└── README.md
```

Created while running: `terraform_runs/` (one folder per request, holds the Terraform state) and `.terraform-plugin-cache/`. Do not delete `terraform_runs/` while servers are running, because Terraform needs it to destroy them.

## 19. Testing checklist

| Area | Test | Expected result |
|---|---|---|
| Login | Wrong password | Error, no login |
| Access | Normal user opens `/admin` | Sent back to the dashboard |
| Access | Not logged in opens `/admin` | Sent to the login page |
| Validation | Storage 5 GB or 50 GB | Refused (8 to 30 allowed) |
| Rejection | Admin rejects with a reason | Status Rejected, user sees the reason |
| Provisioning | Approve a Low, 2-hour request | Provisioning, then Provisioned with a public IP; instance visible in AWS |
| Types | Repeat for Medium and High | Both provision |
| Destroy | Click Destroy | Status Destroyed; AWS shows Terminated |
| Failure | Use a wrong AWS key, then approve | Status Failed with an error and a Retry button (restore the key afterwards) |
| Capacity | Approve more than 4 servers at once | The extra ones fail with `VcpuLimitExceeded`, partial resources are removed |

## 20. Troubleshooting

| Problem | Fix |
|---|---|
| `no such table` | Run `init_db.py` (sections 9 and 10) |
| Backend fails with missing settings | `DATABASE_URL` and `SECRET_KEY` must be set |
| `Extra inputs are not permitted` | An unknown name is in `backend\.env`. Keep only `DATABASE_URL` and `SECRET_KEY` there |
| `No module named sqlalchemy` | Activate the venv first (`.\venv\Scripts\Activate.ps1`) |
| Port 8000 or 5173 already in use | Docker and the terminal way are both running. Stop one |
| Request `failed` with `VcpuLimitExceeded` | Too many servers running (limit 4). Destroy some, then Retry |
| Request `failed` with "not eligible for Free Tier" | That instance type is not allowed on your AWS plan. Use a smaller workload |
| Request `failed`, other error | Open the request and read the red error text; check `docker compose logs backend` or the `uvicorn` window |
| `terraform: not found` | Install Terraform and make sure `terraform -version` works |
| AWS credential errors | Check the keys in `.env` (Docker) or run `aws configure` again (terminal) |
| Changes not showing in Docker | Rebuild: `docker compose up -d --build` |
| Login works but no admin pages | Run `make_admin.py`, then log out and log in again |
| Server still running in AWS but the portal says nothing | Destroy it in the AWS Console: EC2 → Instances → select → Instance state → Terminate |

## 21. Limitations

- SQLite and one backend process: suitable for demos and small teams, not for large production use.
- Only EC2, in one region (`ap-south-1`).
- At most 4 servers run at the same time with the default AWS vCPU quota. Users can still send unlimited requests.
- Cost values are estimates, not a bill.
- Recommendation and security checks are rule-based, not machine learning, and do not replace a full security review.
- No password recovery and no CAPTCHA yet.

## 22. Future scope

- Check the free vCPU capacity before approval, or queue approved requests until a slot is free
- A manager role between the user and the admin (multi-level approval)
- Email notifications and password recovery, CAPTCHA
- More resource types: S3, RDS, VPC, load balancers
- More regions and more clouds (Azure, Google Cloud)
- PostgreSQL for larger deployments
- Machine-learning based recommendation and real-time AWS pricing

## 23. Security notes

- Keep `.env` out of Git. It is already in `.gitignore`.
- Use a dedicated IAM user with only the permissions it needs, and delete its keys when the project is over.
- If a key was ever shown or committed by mistake, delete it in IAM and create a new one.
- Do not commit `*.db`, `*.tfstate` or `terraform_runs/`. They can hold user data and AWS details. They are also in `.gitignore`.

---
## 24.How to setup the a aws the
- main branch there already created all step in details follow all step then you can be used that all thing of configuration all the thins
- The file name is `*READMEAWS.md`
- driect access of the given below
```
https://github.com/Prathamesh13-n/PBL-Sem-V/blob/main/READMEAWS.md
```

*Developed as a PBL project at MIT Art, Design and Technology University, Pune.*
