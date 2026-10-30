# AWS Setup Guide

This guide shows how to prepare an AWS account for the EC2 Provisioning Portal: create a safe IAM user, get access keys, connect them to the portal, check your limits and protect your credits.

Do this **once**, before you run the portal. Back to the main guide: [README.md](../README.md)

## Contents

1. [What you need](#1-what-you-need)
2. [Protect your account first](#2-protect-your-account-first)
3. [Create the IAM user](#3-create-the-iam-user)
4. [Create the access key](#4-create-the-access-key)
5. [Connect the keys to the portal](#5-connect-the-keys-to-the-portal)
6. [Check that it works](#6-check-that-it-works)
7. [Check your vCPU limit](#7-check-your-vcpu-limit)
8. [Set a budget alert](#8-set-a-budget-alert)
9. [Which instance types work](#9-which-instance-types-work)
10. [Clean up and remove access](#10-clean-up-and-remove-access)
11. [Common AWS errors](#11-common-aws-errors)

---

## 1. What you need

- An AWS account (https://aws.amazon.com). A credit card or free-plan sign-up is required by AWS.
- The **AWS region** used by the portal: **Asia Pacific (Mumbai), `ap-south-1`**. Select it in the top-right corner of the Console whenever you look at servers.

The portal uses an **IAM user with access keys**. (An IAM *role* is only needed if you later run the portal itself on an AWS server. For running on your own computer or in Docker, use an IAM user.)

## 2. Protect your account first

1. **Never use the root account keys** for the portal. The root user can do everything, including closing the account.
2. Turn on **multi-factor authentication (MFA)** for the root user: Console → your name (top right) → **Security credentials** → **Assign MFA device**.
3. Use the root login only to create the IAM user below.

## 3. Create the IAM user

1. Sign in to the AWS Console and search for **IAM**, then open it.
2. In the left menu click **Users**, then **Create user**.
3. **User name:** `ec2-portal-user` (any name works).
4. Leave **"Provide user access to the AWS Management Console"** unchecked. This user only needs keys, not a login.
5. Click **Next**.
6. Choose **Attach policies directly**.
7. In the search box type **`AmazonEC2FullAccess`**, tick it, and click **Next**.
8. Click **Create user**.

`AmazonEC2FullAccess` is enough for this project: it lets Terraform create and destroy servers, disks and security groups, and look up the network and the machine image. A stricter custom policy is possible, but it must be tested carefully, because Terraform needs many EC2 actions and a missing one makes provisioning fail.

## 4. Create the access key

1. In IAM → **Users**, click the user you just created.
2. Open the **Security credentials** tab.
3. Scroll to **Access keys** and click **Create access key**.
4. For the use case choose **Command Line Interface (CLI)**, tick the confirmation box, and click **Next**.
5. (Optional) add a description such as `portal`, then click **Create access key**.
6. **Copy the Access key ID and the Secret access key now.** The secret is shown only once. You can also click **Download .csv file** and keep it somewhere safe, outside the project folder.
7. Click **Done**.

**Keep these two values secret.** Do not put them in the README, in Git, in screenshots or in chat messages. If you ever show them by mistake, delete the key in IAM (Security credentials → the key → **Actions → Delete**) and create a new one.

## 5. Connect the keys to the portal

### Docker way

Put the keys in the `.env` file in the project root:

```
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_DEFAULT_REGION=ap-south-1
```

(The same file also holds `DATABASE_URL` and `SECRET_KEY`. See the main README.)

### Terminal way

Install the AWS CLI (https://aws.amazon.com/cli/), then run:

```powershell
aws configure
```

Answer the four questions:

| Question | Answer |
|---|---|
| AWS Access Key ID | the key ID from step 4 |
| AWS Secret Access Key | the secret from step 4 |
| Default region name | `ap-south-1` |
| Default output format | `json` |

The keys are stored in your user folder (`C:\Users\<you>\.aws\`), not in the project, so Git never sees them.

## 6. Check that it works

```powershell
aws sts get-caller-identity
```

It should print your account number and the user name `ec2-portal-user`. If it prints an error, the keys were copied wrongly. Run `aws configure` again.

Then check that you can list servers in Mumbai:

```powershell
aws ec2 describe-instances --region ap-south-1 --query "Reservations[].Instances[].[InstanceId,State.Name]" --output table
```

An empty table means no servers exist yet. This is correct for a new account.

## 7. Check your vCPU limit

AWS limits how many vCPUs can run at once. New accounts usually get **8 vCPUs**. Every instance type used by the portal (`t3.micro`, `t3.small`, `c7i-flex.large`) has 2 vCPUs, so **only 4 servers can run at the same time**. The 5th approved request fails with `VcpuLimitExceeded`.

To see or raise the limit:

1. Console → search **Service Quotas** → **AWS services** → **Amazon Elastic Compute Cloud (Amazon EC2)**.
2. Search for **Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances**.
3. Click it. It shows the applied value (for example 8).
4. Click **Request increase at account level** to ask for more. Approval can take hours or days, and free-plan accounts may be refused.

Make sure the region in the top-right corner is **Mumbai** while you do this.

## 8. Set a budget alert

1. Console → search **Billing and Cost Management** → **Budgets** → **Create budget**.
2. Choose **Use a template (simplified)** → **Zero spend budget** (alerts you as soon as any cost appears) or **Monthly cost budget** with a small amount.
3. Enter your email address and click **Create budget**.

Also look at **Billing → Bills** after each testing day to see what was charged. The cost shown in the portal is only an estimate.

## 9. Which instance types work

| Workload | Instance type | Notes |
|---|---|---|
| Low | `t3.micro` | Free-plan friendly |
| Medium | `t3.small` | Works on the accounts tested |
| High | `c7i-flex.large` | 4 GiB memory. Used instead of `t3.medium` |

`t3.medium` is refused on the AWS Free plan with the error "not eligible for Free Tier", which is why the portal uses `c7i-flex.large` for High workloads. Eligibility depends on your account. If a type is refused, the request shows **Failed** with the AWS message, and you can ask for a smaller workload.

## 10. Clean up and remove access

**After every testing session:**

1. Destroy the servers: `python destroy_all.py --yes` (in the `backend` folder).
2. Open **EC2 → Instances** in **Mumbai**. Every row must say **Terminated** (rows stay visible for about an hour).
3. Open **EC2 → Volumes**. It should be empty.

**When the project is finished:**

1. IAM → Users → your user → **Security credentials** → access key → **Actions → Deactivate**, then **Delete**.
2. Optionally delete the IAM user.
3. Delete the Budgets you do not need.

## 11. Common AWS errors

| Error message | Meaning | Fix |
|---|---|---|
| `VcpuLimitExceeded` | Too many servers are running (8 vCPU limit, 4 servers) | Destroy servers, then **Retry Provisioning**. Or request a higher quota (section 7) |
| `not eligible for Free Tier` | The instance type is not allowed on your plan | Use a smaller workload |
| `InvalidClientTokenId` or `AuthFailure` | Wrong or deleted access key | Check `.env` or run `aws configure` again |
| `UnauthorizedOperation` | The IAM user lacks permission | Attach `AmazonEC2FullAccess` (section 3) |
| `Unable to locate credentials` | The terminal has no keys | Run `aws configure` |
| `No servers visible in the Console` | Wrong region selected | Switch the top-right region to **Mumbai (ap-south-1)** |
| `InstanceLimitExceeded` | Another account limit was reached | Check Service Quotas (section 7) |
