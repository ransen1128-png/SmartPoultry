"""Find a Current Flocks row by its Branch and Flock ID columns.

Flock IDs are numbered per branch, and a short ID such as "12" can also appear in another
column (for example a quantity), so rows are matched on these two columns exactly.
"""

_MATCHES = """([flockId, branch]) => [...document.querySelectorAll('#flocksBody tr')]
    .map((row, index) => ({index, cells: row.cells}))
    .filter(({cells}) => cells.length > 1 && cells[0].textContent.trim() === branch && cells[1].textContent.trim() === flockId)
    .map(({index}) => index)"""


def flock_row(page, flock_id, branch_name, timeout=15000):
    """Wait until exactly one row matches, then return a locator for it."""
    page.wait_for_function(f'(args) => ({_MATCHES})(args).length === 1', arg=[flock_id, branch_name], timeout=timeout)
    index = page.evaluate(f'(args) => ({_MATCHES})(args)[0]', [flock_id, branch_name])
    return page.locator('#flocksBody tr').nth(index)
