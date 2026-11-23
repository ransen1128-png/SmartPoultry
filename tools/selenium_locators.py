"""Selenium locators and assertions shared by the browser cases."""

import re

from selenium.common.exceptions import (
    ElementClickInterceptedException, ElementNotInteractableException,
    NoSuchElementException, StaleElementReferenceException, TimeoutException,
)
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

WAIT_ERRORS = (NoSuchElementException, StaleElementReferenceException,
               ElementClickInterceptedException, ElementNotInteractableException)

QUERY = r"""
const normalize = text => (text || '').trim().replace(/\s+/g, ' ');
const text = el => normalize(el.textContent);
const labels = el => normalize(Array.from(el.labels || [], text).join(' '));
const name = el => normalize(
    el.getAttribute('aria-label') ||
    (el.getAttribute('aria-labelledby') || '').split(/\s+/).map(id => text(document.getElementById(id) || {})).join(' ').trim() ||
    labels(el) || el.getAttribute('alt') || text(el)
);
const visible = el => el.checkVisibility({checkVisibilityCSS: true}) &&
    (el.getClientRects().length || getComputedStyle(el).display === 'contents');
const matches = (value, query) => query == null ||
    (query.regex !== undefined ? new RegExp(query.regex, query.flags).test(value) :
        query.exact ? value === query.text : value.toLowerCase().includes(query.text.toLowerCase()));
const roles = {
    alert:'[role="alert"]', button:'button,input[type=submit],input[type=button]',
    cell:'td', dialog:'dialog[open]', heading:'h1,h2,h3,h4,h5,h6', img:'img',
    link:'a[href]', listitem:'li', region:'section[aria-label],section[aria-labelledby]',
    row:'tr', searchbox:'input[type=search]', switch:'[role="switch"]',
    tab:'[role="tab"]', tabpanel:'[role="tabpanel"]'
};
function query(plan, roots = [document]) {
    for (const [kind, arg] of plan) {
        if (kind === 'css') {
            const selector = arg.replace(/:visible/g, '');
            roots = roots.flatMap(root => Array.from(root.querySelectorAll(selector)));
            if (selector !== arg) roots = roots.filter(visible);
        } else if (kind === 'role') {
            const implicit = roles[arg.role];
            const explicit = '[role="' + arg.role + '"]';
            const selector = implicit ? implicit + ',' + explicit : explicit;
            roots = roots.flatMap(root => Array.from(root.querySelectorAll(selector))).filter(el =>
                (!el.hasAttribute('role') || el.getAttribute('role') === arg.role) &&
                !el.closest('[hidden],[aria-hidden="true"]') && visible(el) &&
                (!arg.level || el.tagName === 'H' + arg.level || el.getAttribute('aria-level') == arg.level) &&
                matches(name(el), arg.name));
        } else if (kind === 'label') {
            roots = roots.flatMap(root => Array.from(root.querySelectorAll('input,textarea,select,button')))
                .filter(el => matches(name(el), arg));
        } else if (kind === 'text') {
            roots = roots.flatMap(root => Array.from(root.querySelectorAll('*'))).filter(el =>
                !el.matches('script,style,template,option') && matches(text(el), arg) &&
                !Array.from(el.children).some(child => matches(text(child), arg)));
        } else if (kind === 'index') {
            const item = roots.at(arg);
            roots = item ? [item] : [];
        } else if (kind === 'and') {
            const other = new Set(query(arg));
            roots = roots.filter(el => other.has(el));
        } else if (kind === 'filter') {
            roots = roots.filter(el => (arg.visible == null || Boolean(visible(el)) === arg.visible) &&
                matches(text(el), arg.text) && (!arg.has || query(arg.has, [el]).length));
        }
        roots = Array.from(new Set(roots));
    }
    return roots;
}
return query(arguments[0]);
"""


def match_spec(value, exact=False):
    if value is None:
        return None
    if isinstance(value, re.Pattern):
        return {'regex': value.pattern, 'flags': 'i' if value.flags & re.I else ''}
    return {'text': value, 'exact': exact}


def matches(value, target, *, contains=False, ignore_case=False):
    if value is None:
        return False
    if isinstance(target, re.Pattern):
        return bool(target.search(value))
    if ignore_case:
        value, target = value.casefold(), target.casefold()
    return target in value if contains else value == target


class Locator:
    def __init__(self, page, plan=()):
        self.page = page
        self.plan = plan

    def _append(self, kind, value):
        return Locator(self.page, (*self.plan, (kind, value)))

    def locator(self, selector):
        return self._append('css', selector)

    def get_by_role(self, role, *, name=None, exact=False, level=None):
        return self._append('role', {'role': role, 'name': match_spec(name, exact), 'level': level})

    def get_by_label(self, label, *, exact=False):
        return self._append('label', match_spec(label, exact))

    def get_by_text(self, text, *, exact=False):
        return self._append('text', match_spec(text, exact))

    def filter(self, *, has=None, has_text=None, visible=None):
        return self._append('filter', {'has': has.plan if has is not None else None,
                                       'text': match_spec(has_text), 'visible': visible})

    def and_(self, other):
        return self._append('and', other.plan)

    def nth(self, index):
        return self._append('index', index)

    @property
    def first(self):
        return self.nth(0)

    @property
    def last(self):
        return self.nth(-1)

    def elements(self):
        return self.page.driver.execute_script(QUERY, self.plan)

    def _one(self):
        elements = self.elements()
        if len(elements) != 1:
            raise NoSuchElementException(f'Expected one match, found {len(elements)} for {self.plan!r}')
        return elements[0]

    def element_handle(self):
        return self.page.wait(self._one)

    def is_visible(self):
        return any(el.is_displayed() for el in self.elements())

    def _interactive(self, element):
        return self.page.driver.execute_script("""
            const modal = arguments[0].closest('.modal');
            return !modal || !window.bootstrap?.Modal?.getInstance(modal)?._isTransitioning;
        """, element) and element.is_displayed() and element.is_enabled()

    def click(self, *, timeout=10000):
        last_error = None

        def click_element():
            nonlocal last_error
            try:
                element = self._one()
                if not self._interactive(element):
                    return False
                self.page.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', inline: 'nearest', behavior: 'instant'});", element,
                )
                element.click()
            except WAIT_ERRORS as exc:
                last_error = exc
                return False
            return True

        try:
            self.page.wait(click_element, timeout)
        except TimeoutException as exc:
            raise AssertionError(f'Could not click {self.plan!r}: {last_error.msg if last_error else ""}') from exc
        self.page.poll_network()

    def evaluate(self, expression, arg=None):
        return self.page.driver.execute_script(f'return ({expression})(arguments[0], arguments[1]);',
                                               self.element_handle(), arg)

    def evaluate_all(self, expression):
        return self.page.driver.execute_script(f'return ({expression})(arguments[0]);', self.elements())

    def fill(self, value):
        field = self.element_handle()
        self.page.driver.execute_script("""
            const [field, value] = arguments;
            if (field.disabled || field.readOnly) throw Error('Field is not editable');
            field.focus();
            field.value = value;
            field.dispatchEvent(new Event('input', {bubbles:true}));
            field.dispatchEvent(new Event('change', {bubbles:true}));
        """, field, str(value))
        if self.input_value() != str(value):
            raise AssertionError(f'Browser rejected the supplied value for {self.plan!r}')

    def select_option(self, value=None, *, label=None, index=None):
        def select():
            return self.page.driver.execute_script("""
                const [field, value, label, index] = arguments;
                const option = Array.from(field.options).find((option, i) =>
                    index !== null ? i === index : label !== null ? option.label.trim() === label : option.value === value);
                if (field.disabled || !option || option.disabled) return false;
                field.selectedIndex = option.index;
                field.dispatchEvent(new Event('input', {bubbles:true}));
                field.dispatchEvent(new Event('change', {bubbles:true}));
                return true;
            """, self._one(), value, label, index)
        self.page.wait(select)
        self.page.poll_network()

    def input_value(self):
        return self.evaluate('el => el.value')

    def get_attribute(self, name):
        return self.element_handle().get_dom_attribute(name)

    def focus(self):
        self.evaluate('el => el.focus()')

    def press(self, key):
        aliases = {'ArrowRight': Keys.ARROW_RIGHT, 'ArrowUp': Keys.ARROW_UP,
                   'Escape': Keys.ESCAPE, 'Enter': Keys.ENTER}
        def focus_field():
            field = self._one()
            if not self._interactive(field):
                return False
            self.page.driver.execute_script("arguments[0].focus();", field)
            return field == self.page.driver.switch_to.active_element

        self.page.wait(focus_field)
        ActionChains(self.page.driver).send_keys(aliases.get(key, key)).perform()

    def inner_text(self):
        return self.evaluate('el => el.innerText')

    def all_text_contents(self):
        return self.evaluate_all('elements => elements.map(el => el.textContent)')

    def uncheck(self):
        if self.element_handle().is_selected():
            self.click()


class Assertions:
    def __init__(self, subject):
        self.subject = subject
        self.page = subject.page if isinstance(subject, Locator) else subject

    def _assert(self, predicate, description, timeout=5000):
        try:
            self.page.wait(predicate, timeout)
        except TimeoutException as exc:
            target = self.subject.plan if isinstance(self.subject, Locator) else self.page.url
            raise AssertionError(f'{description}. Target: {target!r}') from exc

    def to_have_url(self, value, *, timeout=5000):
        self._assert(lambda: matches(self.page.url, value), f'Expected URL {value!r}', timeout)

    def to_be_visible(self, *, timeout=5000):
        self._assert(self.subject.is_visible, 'Expected a visible element', timeout)

    def to_be_hidden(self, *, timeout=5000):
        self._assert(lambda: not self.subject.is_visible(), 'Expected a hidden or absent element', timeout)

    def to_have_count(self, count, *, timeout=5000):
        self._assert(lambda: len(self.subject.elements()) == count, f'Expected {count} elements', timeout)

    def _property(self, read, predicate, description, timeout):
        self._assert(lambda: predicate(read(self.subject._one())), description, timeout)

    def to_be_enabled(self, *, timeout=5000):
        self._property(lambda el: el.is_enabled(), bool, 'Expected an enabled element', timeout)

    def to_be_disabled(self, *, timeout=5000):
        self._property(lambda el: el.is_enabled(), lambda val: not val, 'Expected a disabled element', timeout)

    def to_be_focused(self, *, timeout=5000):
        self._property(lambda el: el == self.page.driver.switch_to.active_element, bool,
                       'Expected a focused element', timeout)

    def to_be_checked(self, *, timeout=5000):
        self._property(lambda el: el.is_selected(), bool, 'Expected a checked element', timeout)

    def not_to_be_checked(self, *, timeout=5000):
        self._property(lambda el: el.is_selected(), lambda val: not val, 'Expected an unchecked element', timeout)

    def _text(self, value, contains, negate, ignore_case, timeout):
        def read(el):
            return self.page.driver.execute_script(
                "return arguments[0].textContent.trim().replace(/\\s+/g, ' ');", el)
        self._property(read, lambda actual: matches(actual, value, contains=contains,
                                                   ignore_case=ignore_case) != negate,
                       f'Expected text {value!r} (contains={contains}, negate={negate})', timeout)

    def to_have_text(self, value, *, timeout=5000, ignore_case=False):
        if isinstance(value, (list, tuple)):
            def sequence_matches():
                texts = self.subject.all_text_contents()
                return len(texts) == len(value) and all(
                    matches(' '.join(actual.split()), expected, ignore_case=ignore_case)
                    for actual, expected in zip(texts, value)
                )
            self._assert(sequence_matches, f'Expected text sequence {value!r}', timeout)
        else:
            self._text(value, False, False, ignore_case, timeout)

    def to_contain_text(self, value, *, timeout=5000, ignore_case=False):
        self._text(value, True, False, ignore_case, timeout)

    def not_to_contain_text(self, value, *, timeout=5000, ignore_case=False):
        self._text(value, True, True, ignore_case, timeout)

    def to_have_attribute(self, name, value, *, timeout=5000):
        self._property(lambda el: el.get_dom_attribute(name), lambda actual: matches(actual, value),
                       f'Expected attribute {name}={value!r}', timeout)

    def not_to_have_attribute(self, name, value, *, timeout=5000):
        self._property(lambda el: el.get_dom_attribute(name), lambda actual: not matches(actual, value),
                       f'Expected attribute {name} to differ from {value!r}', timeout)

    def to_have_value(self, value, *, timeout=5000):
        self._property(lambda el: el.get_property('value'), lambda actual: matches(actual, value),
                       f'Expected field value {value!r}', timeout)

    def to_have_accessible_description(self, value, *, timeout=5000):
        def read(el):
            return self.page.driver.execute_script("""
                return (arguments[0].getAttribute('aria-describedby') || '').split(/\s+/)
                    .map(id => document.getElementById(id)?.textContent || '').join(' ').trim();
            """, el)
        self._property(read, lambda actual: matches(actual, value),
                       f'Expected accessible description {value!r}', timeout)


def expect(subject):
    return Assertions(subject)


def wait_for(driver, predicate, timeout):
    return WebDriverWait(driver, timeout / 1000, poll_frequency=0.1,
                         ignored_exceptions=WAIT_ERRORS).until(lambda _: predicate())
