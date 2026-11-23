# SmartPoultry browser automation

Use Python 3.11. Install Playwright and Chromium with the same Python interpreter you will use for the tests.

```powershell
python -m pip install -r requirements-automation.txt
python -m playwright install chromium
```

From a repository checkout, use `tools/requirements-automation.txt` and `tools/run_automation.py` in the commands below. In the exported folder, use the commands as written.

```powershell
python run_automation.py --list
python run_automation.py --live 1
python run_automation.py --repo "C:\path\to\SMARTPOULTRY" 33
python run_automation.py --repo "C:\path\to\SMARTPOULTRY"
```

The last command runs the local cases. Local cases require a SmartPoultry checkout and its Python dependencies from `requirements.txt`. They run a Django server with an in-memory test database and seed their own data. The runner finds the checkout automatically when invoked from the repository's `tools` folder. An individual local script also accepts `--repo`.

Render cases use the live SmartPoultry site by default. Set `SMARTPOULTRY_TEST_BASE_URL` to use a different deployment. Select them explicitly by number with `--live`. Some need a dedicated test account and may create records or change passwords. Set the applicable environment variables or supply the values at the terminal prompts. In a non-interactive run, cases with missing credentials report a skip and name the required variable. The commonly used variables are `SMARTPOULTRY_TEST_EMAIL`, `SMARTPOULTRY_TEST_USERNAME`, `SMARTPOULTRY_TEST_PASSWORD`, `SMARTPOULTRY_TEST_ADMIN_EMAIL`, `SMARTPOULTRY_TEST_ADMIN_PASSWORD`, `SMARTPOULTRY_TEST_RECOVERY_ANSWER_1`, and `SMARTPOULTRY_TEST_RECOVERY_ANSWER_2`. Run cases that change shared account data serially with your team. Cases 019 and 021 require a new password and leave it in place on the dedicated test account. Set `SMARTPOULTRY_TEST_NEW_PASSWORD` or enter it when prompted.

You can set `SMARTPOULTRY_BROWSER_CHANNEL` to `msedge` or `chrome` to use an installed browser instead of downloaded Chromium. The saved rooster analysis cases use a generated image fixture unless `SMARTPOULTRY_TEST_CHICKEN_IMAGE` names an existing image.

Case 050 currently reports that the site accepts a flock with zero chickens. Run it against a dedicated QA deployment. Cases 141 and 142 cover known Scenario Analysis validation issues. The site currently displays baseline figures for text or blank input, so these cases report a failure until the validation is implemented.

For live flock edit or history cases, supply the existing fixture IDs when prompted or set `SMARTPOULTRY_TEST_FLOCK_ID` and `SMARTPOULTRY_TEST_HISTORY_FLOCK_ID`. Flock IDs are now assigned automatically. The old manual duplicate-entry cases 049 and 055 report a skip when the ID field is read-only.
