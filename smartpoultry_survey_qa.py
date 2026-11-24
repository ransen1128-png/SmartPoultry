"""Preview randomized SmartPoultry test responses in Chrome.

Install: py -m pip install selenium
Run:     py smartpoultry_survey_qa.py
Optional: --seed 42 for reproducible choices, --limit 1 for a quick preview.

The script presses Next and leaves each preview at the final page.
It never presses Submit. The resulting CSV is labeled synthetic.
"""

import argparse
import csv
import json
import random
from pathlib import Path

FORM_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSfocNJ0AJUrMUEyeepDFJCYxfZm-2o405U0MJoOJDIfflHxGw/viewform"
)
TEST_AGES = (34, 27, 46, 31, 39, 52, 25, 36, 43, 29,
             48, 33, 24, 41, 55, 28, 37, 23, 44, 30)
RECOMMENDATIONS = (
    "Show feed levels and reorder reminders on the dashboard.",
    "Allow farm staff to save flock counts offline.",
    "Include a weekly summary of mortality rates by branch.",
    "Let users compare egg production across different flocks.",
    "Add an export for feed usage and inventory adjustments.",
    "Send a reminder when a broiler flock reaches harvest age.",
    "Let supervisors review changes to production records.",
    "Make the expense breakdown easier to read on small screens.",
    "Provide a printable receipt with separate lines for egg sizes.",
    "Add a branch selector to the monthly performance report.",
    "Show chick purchase and delivery costs on the same record.",
    "Provide an alert when recorded sales exceed available stock.",
    "Add a preview before applying a price-change scenario.",
    "Give each branch its own feed shortage threshold.",
    "Show the forecast period and data used for each prediction.",
    "Let staff search flock history by date range.",
    "Show what changed when a mortality record is corrected.",
    "Add a backup status indicator for farm managers.",
    "Include a short guide for setting up account recovery.",
    "Highlight unfamiliar terms such as available stock and assigned cost.",
)
DEMOGRAPHIC_FIELDS = ("First name", "Last name", "Age")


def visible(parent, selector):
    return [
        element for element in parent.find_elements("css selector", selector)
        if element.is_displayed()
    ]


def answer_label(element):
    return (
        element.get_dom_attribute("aria-label")
        or element.get_dom_attribute("data-value")
        or element.text
    ).strip()


def fill_page(driver, blocks, participant, rng, wait, answers, recommendation):
    for position, block in enumerate(blocks, start=1):
        headings = visible(block, '[role="heading"], h1, h2, h3')
        title = headings[0].text.strip().rstrip("* ").strip() if headings else ""
        fields = visible(block, 'input:not([type="hidden"]), textarea')
        demographic = dict(zip(map(str.casefold, DEMOGRAPHIC_FIELDS), participant))
        if title.casefold() in demographic:
            if len(fields) != 1:
                raise RuntimeError(f"Expected one text field for {title}")
            fields[0].clear()
            fields[0].send_keys(demographic[title.casefold()])
            continue

        # Google Forms uses one radiogroup per question or per grid row.
        radio_groups = visible(block, '[role="radiogroup"]') or [block]
        selections = []
        for group in radio_groups:
            radios = [
                option for option in visible(group, '[role="radio"]')
                if option.get_dom_attribute("data-value") != "__other_option__"
            ]
            if radios:
                choice = rng.choice(radios)
                choice.click()
                selections.append(answer_label(choice))

        # Checkbox grids use one accessible group per row.
        checkboxes = visible(block, '[role="checkbox"]')
        if checkboxes:
            groups = [
                visible(group, '[role="checkbox"]')
                for group in visible(block, '[role="group"]')
            ]
            groups = [group for group in groups if group]
            if not groups or sum(map(len, groups)) != len(checkboxes):
                groups = [checkboxes]
            for group in groups:
                options = [
                    option for option in group
                    if option.get_dom_attribute("data-value") != "__other_option__"
                ]
                if options:
                    choice = rng.choice(options)
                    choice.click()
                    selections.append(answer_label(choice))

        for dropdown in visible(block, '[role="listbox"]'):
            if dropdown.get_dom_attribute("aria-expanded") != "true":
                dropdown.click()
            options = wait.until(
                lambda _: [
                    option for option in visible(dropdown, '[role="option"]')
                    if option.get_dom_attribute("data-value") not in (None, "")
                ],
                message=f"No selectable dropdown options for {title}",
            )
            choice = rng.choice(options)
            selections.append(answer_label(choice))
            choice.click()

        if selections:
            answers.append((title or f"Untitled question {position}", selections))
        elif fields and len(fields) == 1 and fields[0].get_dom_attribute("type") in (
            None, "text"
        ):
            # Use an explicit test marker for open-ended answers.
            fields[0].clear()
            value = f"[SYNTHETIC QA] {recommendation}"
            fields[0].send_keys(value)
        elif fields or block.find_elements("css selector", "[aria-required=true], [role=slider]"):
            raise RuntimeError(f"Unsupported question type: {title or position}")


def preview(driver, wait, participant, rng, recommendation):
    driver.get(FORM_URL + "?hl=en")
    answers = []
    for _ in range(15):
        def fill_current_page(active):
            blocks = visible(active, 'form [role="listitem"]')
            if not blocks or active.execute_script("return document.readyState") != "complete":
                return False
            page_answers = []
            fill_page(active, blocks, participant, rng, wait, page_answers, recommendation)
            answers.extend(page_answers)
            return blocks

        blocks = wait.until(fill_current_page, message="Could not fill the visible survey questions.")
        actions = {
            element.text.strip().casefold(): element
            for element in visible(driver, 'form [role="button"], form button')
        }
        if "submit" in actions or "isumite" in actions:
            return answers
        next_button = actions.get("next") or actions.get("susunod")
        if next_button is None:
            raise RuntimeError("Could not find the Next or Submit button.")
        next_button.click()
        wait.until(
            lambda active: (current := visible(active, 'form [role="listitem"]'))
            and not set(blocks).intersection(current),
            message="Next did not advance. Check this page for a validation message.",
        )
    raise RuntimeError("The form exceeded the section limit.")


def answer_pattern(answers):
    return json.dumps(answers, ensure_ascii=False)


def run(args, driver, wait):
    participants = [('QA', f'Respondent {i:02}', str(age))
                    for i, age in enumerate(TEST_AGES[:args.limit], 1)]
    recommendations = list(RECOMMENDATIONS)
    rng = random.Random(args.seed)
    rng.shuffle(recommendations)
    seen = set()
    with args.output.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.writer(output)
        writer.writerow(("Response type", *DEMOGRAPHIC_FIELDS, "Answers (JSON)", "Recommendation"))
        for index, participant in enumerate(participants, start=1):
            for _ in range(20):
                recommendation = recommendations[index - 1]
                result = answer_pattern(preview(driver, wait, participant, rng, recommendation))
                if result not in seen:
                    break
            else:
                raise RuntimeError(
                    f"Could not find another unique answer pattern for entry {index}."
                )
            seen.add(result)
            writer.writerow(("Synthetic test", *participant, result, recommendation))
            output.flush()
            print(f"[{index}/{len(participants)}] {' '.join(participant[:2])} previewed.")
            if not args.no_pause:
                input("Review the final page, then press Enter here to continue. ")
    print(f"Synthetic previews saved to {args.output.resolve()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, help="Reproduce the same random choices")
    parser.add_argument("--limit", type=int, default=20, choices=range(1, 21))
    parser.add_argument("--no-pause", action="store_true", help="Advance automatically")
    parser.add_argument("--output", type=Path, default=Path("synthetic_previews.csv"))
    args = parser.parse_args()

    try:
        from selenium import webdriver
        from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError:
        parser.exit(1, "Selenium is required. Install it with: py -m pip install selenium\n")

    try:
        with webdriver.Chrome() as driver:
            run(args, driver, WebDriverWait(driver, 15, ignored_exceptions=(StaleElementReferenceException,)))
    except (RuntimeError, WebDriverException) as error:
        parser.exit(1, f"Preview stopped: {getattr(error, 'msg', str(error))}\n")


if __name__ == "__main__":
    main()
