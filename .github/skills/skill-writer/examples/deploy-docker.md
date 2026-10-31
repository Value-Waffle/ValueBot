> **Example only** — a real SKILL.md for deploying Docker. Copy to `.github/skills/deploy-docker/SKILL.md` to use.

```markdown
---
name: deploy-docker
description: 'Deploy a Docker Compose stack to a remote server via SSH. Use when: deploying, redeploying, or updating a Docker-based service on a remote host.'
user-invocable: true
---

# Deploy Docker Stack

Deploy or update a Docker Compose application on a remote server.

## When to Use
- Deploying a Docker Compose stack to production/staging
- Redeploying after configuration changes
- Rolling back to a previous version

## Prerequisites
- `docker` and `docker compose` installed locally
- SSH access to the target server
- `deploy.env` file with `SSH_HOST`, `SSH_USER`, `STACK_PATH` variables

## Procedure
1. **Build images** — `docker compose build` in project root.
2. **Push images** — `docker compose push` (if using a registry).
3. **Copy compose file** — `scp docker-compose.yml $SSH_USER@$SSH_HOST:$STACK_PATH/`
4. **SSH and redeploy** — `ssh $SSH_USER@$SSH_HOST "cd $STACK_PATH && docker compose pull && docker compose up -d"`
5. **Verify** — `ssh $SSH_USER@$SSH_HOST "docker compose ps"` — all services should show `Up`.

## Rollback
```bash
ssh $SSH_USER@$SSH_HOST "cd $STACK_PATH && docker compose down && docker compose -f docker-compose.previous.yml up -d"
```

## Troubleshooting
- **Connection refused**: Check `SSH_HOST` and that the server is running.
- **Image not found**: Ensure `docker compose push` succeeded and the tag is correct.
- **Port conflict**: Run `docker compose down` on the server first.
```
