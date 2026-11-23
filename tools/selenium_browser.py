"""Selenium WebDriver sessions and browser events for the QA suite."""

from contextlib import contextmanager
from dataclasses import dataclass
import base64
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
from selenium.webdriver import ActionChains

try:
    from tools.selenium_locators import Locator, expect, wait_for
except ModuleNotFoundError:
    from selenium_locators import Locator, expect, wait_for


@dataclass
class Request:
    url: str
    method: str
    post_data: str = ''

    @property
    def post_data_json(self):
        return json.loads(self.post_data)


@dataclass
class Response:
    url: str
    status: int
    request: Request
    body: object

    @property
    def ok(self):
        return 200 <= self.status < 300

    def text(self):
        return self.body()

    def json(self):
        return json.loads(self.text())


class BrowserPage(Locator):
    def __init__(self, driver, directory):
        super().__init__(self)
        self.driver = driver
        self.closed = False
        self.directory = directory
        self.requests = {}
        self.responses = []
        self.listeners = {'request': [], 'response': []}
        self.clock = self
        self.request = self
        self.keyboard = self
        self.driver.execute_cdp_cmd('Network.enable', {})
        self.driver.execute_cdp_cmd('Browser.setDownloadBehavior', {
            'behavior': 'allow', 'downloadPath': directory.name,
        })

    @property
    def url(self):
        return self.driver.current_url

    def wait(self, predicate, timeout=10000):
        return wait_for(self.driver, predicate, timeout)

    def goto(self, url, *, timeout=90000, wait_until=None):
        self.driver.set_page_load_timeout(timeout / 1000)
        self.driver.get(url)
        self.poll_network()
        return next((response for response in reversed(self.responses) if response.url == self.url), None)

    def reload(self, *, wait_until=None):
        self.driver.refresh()
        self.poll_network()

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.driver.quit()
        finally:
            self.directory.cleanup()

    def evaluate(self, expression, arg=None):
        return self.driver.execute_script(f'return ({expression})(arguments[0]);', arg)

    def wait_for_function(self, expression, *, arg=None, timeout=10000):
        self.wait(lambda: self.driver.execute_script(f'return ({expression})(arguments[0]);', arg), timeout)

    def type(self, value):
        ActionChains(self.driver).send_keys(value).perform()

    def set_fixed_time(self, date):
        timestamp = round(date.timestamp() * 1000)
        script = """
            (() => {
                const RealDate = Date;
                function FixedDate(...args) {
                    if (!new.target) return new RealDate(FIXED_TIME).toString();
                    return args.length ? new RealDate(...args) : new RealDate(FIXED_TIME);
                }
                Object.setPrototypeOf(FixedDate, RealDate);
                FixedDate.prototype = RealDate.prototype;
                FixedDate.now = () => FIXED_TIME;
                window.Date = FixedDate;
            })();
        """.replace('FIXED_TIME', str(timestamp))
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': script})
        self.driver.execute_script(script)

    def get(self, url):
        status, final_url, body = self.driver.execute_async_script("""
            const [url, done] = arguments;
            fetch(url).then(async response => done([response.status, response.url, await response.text()]))
                .catch(error => done([0, url, String(error)]));
        """, url)
        return Response(final_url, status, Request(url, 'GET'), lambda: body)

    def on(self, event, callback):
        self.poll_network()
        self.listeners[event].append(callback)

    def remove_listener(self, event, callback):
        self.poll_network()
        self.listeners[event].remove(callback)

    def _body(self, request_id):
        def load():
            try:
                return (self.driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id}),)
            except WebDriverException as exc:
                if 'No resource' not in exc.msg and 'No data' not in exc.msg:
                    raise
                return False
        result = self.wait(load)[0]
        if result['base64Encoded']:
            return base64.b64decode(result['body']).decode('utf-8')
        return result['body']

    def poll_network(self):
        for entry in self.driver.get_log('performance'):
            event = json.loads(entry['message'])['message']
            method = event['method']
            if method == 'Network.requestWillBeSent':
                params = event['params']
                data = params['request']
                request = Request(data['url'], data['method'], data.get('postData', ''))
                self.requests[params['requestId']] = request
                for callback in self.listeners['request']:
                    callback(request)
            elif method == 'Network.responseReceived':
                params = event['params']
                request_id = params['requestId']
                if request_id not in self.requests:
                    continue
                data = params['response']
                response = Response(data['url'], data['status'], self.requests[request_id],
                                    lambda rid=request_id: self._body(rid))
                self.responses.append(response)
                for callback in self.listeners['response']:
                    callback(response)

    @contextmanager
    def expect_response(self, predicate, *, timeout=30000):
        self.poll_network()
        first = len(self.responses)
        result = SimpleNamespace()
        yield result

        def matching_response():
            self.poll_network()
            return next((r for r in self.responses[first:] if predicate(r)), False)
        result.value = self.wait(matching_response, timeout)

    @contextmanager
    def expect_navigation(self, *, wait_until=None):
        original = self.url
        document = self.locator('html').element_handle()
        yield

        def navigated():
            try:
                return self.url != original or not document.is_enabled()
            except StaleElementReferenceException:
                return True
        self.wait(navigated)
        self.wait(lambda: self.driver.execute_script("return document.readyState !== 'loading'"))

    @contextmanager
    def expect_download(self):
        directory = Path(self.directory.name)
        before = set(directory.iterdir())
        result = SimpleNamespace()
        yield result

        def completed_file():
            return next((path for path in directory.iterdir()
                         if path not in before and path.suffix.lower() == '.csv'), False)
        result.value = SimpleNamespace(suggested_filename=self.wait(completed_file, 30000).name)


class SeleniumBrowser:
    def __init__(self):
        self.pages = []

    def new_page(self, *, locale='en-US'):
        directory = TemporaryDirectory(prefix='smartpoultry-selenium-')
        channel = os.environ.get('SMARTPOULTRY_BROWSER_CHANNEL', 'chrome').lower()
        if channel not in ('chrome', 'chromium', 'msedge'):
            raise ValueError('SMARTPOULTRY_BROWSER_CHANNEL must be chrome, chromium, or msedge.')
        edge = channel == 'msedge'
        options = webdriver.EdgeOptions() if edge else webdriver.ChromeOptions()
        if binary := os.environ.get('SMARTPOULTRY_BROWSER_BINARY'):
            options.binary_location = binary
        options.add_argument('--headless=new')
        options.add_argument('--window-size=1440,1000')
        options.add_argument(f'--lang={locale}')
        options.page_load_strategy = 'eager'
        options.add_experimental_option('prefs', {'intl.accept_languages': locale})
        options.set_capability('ms:loggingPrefs' if edge else 'goog:loggingPrefs', {'performance': 'ALL'})
        driver = None
        try:
            driver = (webdriver.Edge if edge else webdriver.Chrome)(options=options)
            driver.execute_cdp_cmd('Emulation.setTimezoneOverride', {'timezoneId': 'UTC'})
            page = BrowserPage(driver, directory)
        except Exception:
            if driver is not None:
                driver.quit()
            directory.cleanup()
            raise
        self.pages.append(page)
        return page

    def close(self):
        while self.pages:
            page = self.pages.pop()
            page.close()


def launch_browser():
    return SeleniumBrowser()
