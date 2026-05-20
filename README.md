## Internship Finder

Local internship search and application tracker for Austin-area roles.

### Setup

1. Run `./setup.sh` or install the requirements manually.
2. Fill in `.env` with your personal details and any email or login credentials you want the app to use.
3. Put your resume in `private/resume/` and set `RESUME_PATH` in `.env` to that file.
4. Run `python main.py search` to collect listings.

### Privacy Notes

- `config.yaml` now keeps personal values out of the repo by reading them from environment variables.
- `.env` is ignored by git.
- `private/resume/` is ignored by git so your resume stays local.
