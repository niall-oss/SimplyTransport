This folder contains sample configuration files for deploying the application on Linux.
This includes a config file for Nginx and Supervisor.

## Python version (3.14.3)

The canonical runtime is **Python 3.14.3**; [`pyproject.toml`](../pyproject.toml) allows **>=3.14.3,<3.15** (any security patch in the 3.14 line from 3.14.3 upward). Avoid pre-release alphas/betas in production. On the Ubuntu server:

1. Install Python (for example with [uv](https://github.com/astral-sh/uv): `uv python install 3.14.3`, or your preferred method such as the [deadsnakes](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) PPA if it provides 3.14.3).
2. From the project root, **recreate** the virtualenv used by Supervisor (see `supervisor_config.txt`, typically `venv` or `.venv`):

   ```bash
   rm -rf venv
   uv venv --python 3.14.3 venv
   source venv/bin/activate
   uv pip install -r requirements-top-level.txt
   ```

3. If a dependency has no wheel and compiles a C extension, install build tools first: `sudo apt install -y build-essential python3-dev`.
4. Reload the app: `supervisorctl restart simplytransport` (or your equivalent).

`deploy.sh` runs `git pull`, `uv pip install -r requirements-top-level.txt` into `venv`, then restarts Supervisor. It does not upgrade the Python interpreter—recreate `venv` manually when you change the runtime version (see above).
