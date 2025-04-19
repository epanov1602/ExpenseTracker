import pandas as pd
import numpy as np
import calendar
import datetime
import logging
import pickle
import os

import ipywidgets as widgets
from ipyfilechooser import FileChooser
from IPython.display import display, clear_output, Javascript
from scripts.regsetup import description

DATE_FORMAT = "%Y-%m-%d"

GLOBAL_EXPENSE_FILE = "expense_list.pkl"

GLOBAL_EXPENSE_LIST = pickle.load(open(GLOBAL_EXPENSE_FILE, 'rb')) if os.path.isfile(GLOBAL_EXPENSE_FILE) else []


# a hidden output widget to capture the JavaScript execution
NOTIFY_OUTPUT = widgets.Output()
display(NOTIFY_OUTPUT)


@NOTIFY_OUTPUT.capture()
def popup(text):
    clear_output(wait=True)
    text = text.replace('\\', '/').replace("'", '"')
    display(Javascript(f"alert('{text}')"))


def store_expense_list():
    with open(GLOBAL_EXPENSE_FILE, 'wb') as f:  # open a text file
        pickle.dump(GLOBAL_EXPENSE_LIST, f)  # serialize the list


def _date_options(num_past_dates):
    result = pd.Timestamp.today().date() + np.array(
        [pd.Timedelta(n_days, "D") for n_days in range(-num_past_dates, +1, 1)]
    )
    return [d.strftime(DATE_FORMAT) for d in result]


def confirm_save(**kwargs):
    cleanup_list = []

    def cleanup():
        for item in cleanup_list:
            item.close()

    # a function to be called when the user confirms
    def confirm_action(button):
        GLOBAL_EXPENSE_LIST.append(kwargs)
        store_expense_list()
        cleanup()

    # a function to be called when the user cancels
    def cancel_action(button):
        cleanup()

    # the dialog
    prompt_text = widgets.Label(value=f"Save {kwargs} ?")
    confirm_button = widgets.Button(description="Confirm")
    cancel_button = widgets.Button(description="Cancel")

    # event handlers to the buttons
    confirm_button.on_click(confirm_action)
    cancel_button.on_click(cancel_action)

    # container to hold the dialog elements
    dialog_box = widgets.VBox([prompt_text, confirm_button, cancel_button])
    cleanup_list += [dialog_box]

    # display the dialog
    display(dialog_box)


def new_expense_form():
    return widgets.interactive(
        confirm_save,
        dict(manual=True, manual_name="Save"),
        expense_date=sorted(_date_options(num_past_dates=10)),
        amount=widgets.FloatSlider(min=1.0, max=400, step=1, value=1.0),
        category=frozenset(["Food", "Travel", "School", "Toys", "Wife"]),
        description=""
    )


def view_expenses():
    return widgets.interactive(lambda: display(_get_expenses_df()))


def run_budget_check(limit):
    this_month = _all_days_of_month(pd.Timestamp.today().date())
    expenses_of_this_month = [row for row in GLOBAL_EXPENSE_LIST if row.get("expense_date") in this_month]
    spent = sum(row.get("amount", 0.0) for row in expenses_of_this_month)
    if spent > limit:
        logging.warning("budget exceeded!")
    print(f"{limit - spent} left for the month (spent {spent} out of {limit})")
    return widgets.interactive(lambda: display(pd.DataFrame(expenses_of_this_month)))


def budget_check():
    return widgets.interactive(
        run_budget_check,
        limit=widgets.FloatText(4_000),
    )


def save_to_csv():
    fc = FileChooser()
    fc.filter_pattern = ['*.csv']

    def store_expenses(chooser):
        if chooser.selected is not None:
            df = _get_expenses_df()
            df.to_csv(chooser.selected)
            chooser.close()
            popup("saved to CSV file")

    fc.register_callback(store_expenses)
    return fc


def load_from_csv():
    fc = FileChooser()
    fc.filter_pattern = ['*.csv']

    def load_expenses(chooser):
        global GLOBAL_EXPENSE_LIST

        if chooser.selected is not None:
            df = pd.read_csv(chooser.selected)
            GLOBAL_EXPENSE_LIST = df.to_dict('records')
            chooser.close()
            store_expense_list()
            popup(f"expenses loaded from {chooser.selected}")

    fc.register_callback(load_expenses)
    return fc


def show_menu():
    cleanup_list = []

    special_output = widgets.Output()
    display(special_output)

    def display_next_item(item=None):
        for i in cleanup_list:
            i.close()
        if item is not None:
            special_output.append_display_data(item())

    # event handlers to the buttons
    new_expense_tab = widgets.Button(description="Add Expense")
    new_expense_tab.on_click(lambda button: display_next_item(new_expense_form))

    view_expenses_table = widgets.Button(description="View Expenses")
    view_expenses_table.on_click(lambda button: display_next_item(view_expenses))

    budget_check_table = widgets.Button(description="Budget Check")
    budget_check_table.on_click(lambda button: display_next_item(budget_check))

    to_csv_dialog = widgets.Button(description="To CSV")
    to_csv_dialog.on_click(lambda button: display_next_item(save_to_csv))

    from_csv_dialog = widgets.Button(description="From CSV")
    from_csv_dialog.on_click(lambda button: display_next_item(load_from_csv))

    dialog_box = widgets.VBox([
        new_expense_tab,
        view_expenses_table,
        budget_check_table,
        to_csv_dialog,
        from_csv_dialog,
    ])
    cleanup_list += [dialog_box]
    display(dialog_box)


def _get_expenses_df(dates=None):
    rows = []
    required_attrs = ["expense_date", "amount", "category", "description"]
    for row in GLOBAL_EXPENSE_LIST:
        missing = [a for a in required_attrs if a not in row]
        if missing:
            logging.warning(f"ignoring an expense record (missing fields: {missing}, ignored: {row}")
            continue
        if dates is not None and row.get("expense_date") not in dates:
            continue
        rows.append(row)
    return pd.DataFrame(rows)


def _all_days_of_month(d):
    num_days = calendar.monthrange(d.year, d.month)[1]
    return set([datetime.date(d.year, d.month, day).strftime(DATE_FORMAT) for day in range(1, num_days+1)])
