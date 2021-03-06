# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import urlparse

import error
import transport


element_key = "element-6066-11e4-a52e-4f735466cecf"


def command(func):
    def inner(self, *args, **kwargs):
        if hasattr(self, "session"):
            session = self.session
        else:
            session = self

        if session.session_id is None:
            session.start()
        assert session.session_id != None

        return func(self, *args, **kwargs)

    inner.__name__ = func.__name__
    inner.__doc__ = func.__doc__

    return inner


class Timeouts(object):

    def __init__(self, session):
        self.session = session

    def _get(self, key=None):
        timeouts = self.session.send_command("GET", "timeouts")
        if key is not None:
            return timeouts[key]
        return timeouts

    def _set(self, key, secs):
        body = {key: secs * 1000}
        timeouts = self.session.send_command("POST", "timeouts", body)
        return timeouts[key]

    @property
    def script(self):
        return self._get("script")

    @script.setter
    def script(self, secs):
        return self._set("script", secs)

    @property
    def page_load(self):
        return self._get("pageLoad")

    @page_load.setter
    def page_load(self, secs):
        return self._set("pageLoad", secs)

    @property
    def implicit(self):
        return self._get("implicit")

    @implicit.setter
    def implicit(self, secs):
        return self._set("implicit", secs)

    def __str__(self):
        name = "%s.%s" % (self.__module__, self.__class__.__name__)
        return "<%s script=%d, load=%d, implicit=%d>" % \
            (name, self.script, self.page_load, self.implicit)


class ActionSequence(object):
    """API for creating and performing action sequences.

    Each action method adds one or more actions to a queue. When perform()
    is called, the queued actions fire in order.

    May be chained together as in::

         ActionSequence(session, "key", id) \
            .key_down("a") \
            .key_up("a") \
            .perform()
    """
    def __init__(self, session, action_type, input_id):
        """Represents a sequence of actions of one type for one input source.

        :param session: WebDriver session.
        :param action_type: Action type; may be "none", "key", or "pointer".
        :param input_id: ID of input source.
        """
        self.session = session
        # TODO take advantage of remote end generating uuid
        self._id = input_id
        self._type = action_type
        self._actions = []

    @property
    def dict(self):
        return {
          "type": self._type,
          "id": self._id,
          "actions": self._actions,
        }

    @command
    def perform(self):
        """Perform all queued actions."""
        self.session.actions.perform([self.dict])

    def _key_action(self, subtype, value):
        self._actions.append({"type": subtype, "value": value})

    def key_up(self, value):
        """Queue a keyUp action for `value`.

        :param value: Character to perform key action with.
        """
        self._key_action("keyUp", value)
        return self

    def key_down(self, value):
        """Queue a keyDown action for `value`.

        :param value: Character to perform key action with.
        """
        self._key_action("keyDown", value)
        return self

    def send_keys(self, keys):
        """Queue a keyDown and keyUp action for each character in `keys`.

        :param keys: String of keys to perform key actions with.
        """
        for c in keys:
            self.key_down(c)
            self.key_up(c)
        return self


class Actions(object):
    def __init__(self, session):
        self.session = session

    @command
    def perform(self, actions=None):
        """Performs actions by tick from each action sequence in `actions`.

        :param actions: List of input source action sequences. A single action
                        sequence may be created with the help of
                        ``ActionSequence.dict``.
        """
        body = {"actions": [] if actions is None else actions}
        return self.session.send_command("POST", "actions", body)

    @command
    def release(self):
        return self.session.send_command("DELETE", "actions")

    def sequence(self, *args, **kwargs):
        """Return an empty ActionSequence of the designated type.

        See ActionSequence for parameter list.
        """
        return ActionSequence(self.session, *args, **kwargs)

class Window(object):
    def __init__(self, session):
        self.session = session

    @property
    @command
    def size(self):
        resp = self.session.send_command("GET", "window/rect")
        return (resp["width"], resp["height"])

    @size.setter
    @command
    def size(self, (width, height)):
        body = {"width": width, "height": height}
        self.session.send_command("POST", "window/rect", body)

    @property
    @command
    def position(self):
        resp = self.session.send_command("GET", "window/rect")
        return (resp["x"], resp["y"])

    @position.setter
    @command
    def position(self, (x, y)):
        body = {"x": x, "y": y}
        self.session.send_command("POST", "window/rect", body)

    @property
    @command
    def maximize(self):
        return self.session.send_command("POST", "window/maximize")


class Find(object):
    def __init__(self, session):
        self.session = session

    @command
    def css(self, selector, all=True):
        return self._find_element("css selector", selector, all)

    def _find_element(self, strategy, selector, all):
        route = "elements" if all else "element"

        body = {"using": strategy,
                "value": selector}

        data = self.session.send_command("POST", route, body)

        if all:
            rv = [self.session._element(item) for item in data]
        else:
            rv = self.session._element(data)

        return rv


class Cookies(object):
    def __init__(self, session):
        self.session = session

    def __getitem__(self, name):
        self.session.send_command("GET", "cookie/%s" % name, {})

    def __setitem__(self, name, value):
        cookie = {"name": name,
                  "value": None}

        if isinstance(name, (str, unicode)):
            cookie["value"] = value
        elif hasattr(value, "value"):
            cookie["value"] = value.value
        self.session.send_command("POST", "cookie/%s" % name, {})


class UserPrompt(object):
    def __init__(self, session):
        self.session = session

    @command
    def dismiss(self):
        self.session.send_command("POST", "alert/dismiss")

    @command
    def accept(self):
        self.session.send_command("POST", "alert/accept")

    @property
    @command
    def text(self):
        return self.session.send_command("GET", "alert/text")

    @text.setter
    @command
    def text(self, value):
        body = {"value": list(value)}
        self.session.send_command("POST", "alert/text", body=body)


class Session(object):
    def __init__(self, host, port, url_prefix="/", desired_capabilities=None,
                 required_capabilities=None, timeout=transport.HTTP_TIMEOUT,
                 extension=None):
        self.transport = transport.HTTPWireProtocol(
            host, port, url_prefix, timeout=timeout)
        self.desired_capabilities = desired_capabilities
        self.required_capabilities = required_capabilities
        self.session_id = None
        self.timeouts = None
        self.window = None
        self.find = None
        self._element_cache = {}
        self.extension = None
        self.extension_cls = extension

        self.timeouts = Timeouts(self)
        self.window = Window(self)
        self.find = Find(self)
        self.alert = UserPrompt(self)
        self.actions = Actions(self)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args, **kwargs):
        self.end()

    def __del__(self):
        self.end()

    def start(self):
        if self.session_id is not None:
            return

        body = {}

        caps = {}
        if self.desired_capabilities is not None:
            caps["desiredCapabilities"] = self.desired_capabilities
        if self.required_capabilities is not None:
            caps["requiredCapabilities"] = self.required_capabilities
        #body["capabilities"] = caps
        body = caps

        response = self.send_raw_command("POST", "session", body=body)

        self.session_id = response.body["value"]["sessionId"]

        if self.extension_cls:
            self.extension = self.extension_cls(self)

        return response.body["value"]

    def end(self):
        if self.session_id is None:
            return

        url = "session/%s" % self.session_id
        self.send_raw_command("DELETE", url)

        self.session_id = None
        self.timeouts = None
        self.window = None
        self.find = None
        self.extension = None

    def send_raw_command(self, method, url, body=None, headers=None):
        """
        Send a raw unchecked and unaltered command to the remote end,
        even when there is no active session.

        :param method: HTTP method to use in request.
        :param url: Full request URL.
        :param body: Optional body of the HTTP request.
        :param headers: Optional additional headers to include in the
            HTTP request.

        :return: Instance of ``transport.Response`` describing the HTTP
            response received from the remote end.

        :raises error.WebDriverException: If the remote end returns
            an error.
        """
        response = self.transport.send(method, url, body, headers)
        if response.status != 200:
            value = response.body["value"]
            cls = error.get(value.get("error"))
            raise cls(value.get("message"))
        return response

    def send_command(self, method, uri, body=None):
        """
        Send a command to the remote end and validate its success.

        :param method: HTTP method to use in request.
        :param uri: "Command part" of the HTTP request URL,
            e.g. `window/rect`.
        :param body: Optional body of the HTTP request.

        :return: `None` if the HTTP response body was empty, otherwise
            the result of parsing the body as JSON.

        :raises error.SessionNotCreatedException: If there is no active
            session.
        :raises error.WebDriverException: If the remote end returns
            an error.
        """
        if self.session_id is None:
            raise error.SessionNotCreatedException()

        url = urlparse.urljoin("session/%s/" % self.session_id, uri)
        response = self.send_raw_command(method, url, body)

        rv = response.body["value"]
        if not rv:
            rv = None

        return rv

    @property
    @command
    def url(self):
        return self.send_command("GET", "url")

    @url.setter
    @command
    def url(self, url):
        if urlparse.urlsplit(url).netloc is None:
            return self.url(url)
        body = {"url": url}
        return self.send_command("POST", "url", body)

    @command
    def back(self):
        return self.send_command("POST", "back")

    @command
    def forward(self):
        return self.send_command("POST", "forward")

    @command
    def refresh(self):
        return self.send_command("POST", "refresh")

    @property
    @command
    def title(self):
        return self.send_command("GET", "title")

    @property
    @command
    def window_handle(self):
        return self.send_command("GET", "window")

    @window_handle.setter
    @command
    def window_handle(self, handle):
        body = {"handle": handle}
        return self.send_command("POST", "window", body=body)

    def switch_frame(self, frame):
        if frame == "parent":
            url = "frame/parent"
            body = None
        else:
            url = "frame"
            if isinstance(frame, Element):
                body = {"id": frame.json()}
            else:
                body = {"id": frame}

        return self.send_command("POST", url, body)

    @command
    def close(self):
        return self.send_command("DELETE", "window")

    @property
    @command
    def handles(self):
        return self.send_command("GET", "window/handles")

    @property
    @command
    def active_element(self):
        data = self.send_command("GET", "element/active")
        if data is not None:
            return self._element(data)

    def _element(self, data):
        elem_id = data[element_key]
        assert elem_id
        if elem_id in self._element_cache:
            return self._element_cache[elem_id]
        return Element(self, elem_id)

    @command
    def cookies(self, name=None):
        if name is None:
            url = "cookie"
        else:
            url = "cookie/%s" % name
        return self.send_command("GET", url, {})

    @command
    def set_cookie(self, name, value, path=None, domain=None, secure=None, expiry=None):
        body = {"name": name,
                "value": value}
        if path is not None:
            body["path"] = path
        if domain is not None:
            body["domain"] = domain
        if secure is not None:
            body["secure"] = secure
        if expiry is not None:
            body["expiry"] = expiry
        self.send_command("POST", "cookie", {"cookie": body})

    def delete_cookie(self, name=None):
        if name is None:
            url = "cookie"
        else:
            url = "cookie/%s" % name
        self.send_command("DELETE", url, {})

    #[...]

    @command
    def execute_script(self, script, args=None):
        if args is None:
            args = []

        body = {
            "script": script,
            "args": args
        }
        return self.send_command("POST", "execute/sync", body)

    @command
    def execute_async_script(self, script, args=None):
        if args is None:
            args = []

        body = {
            "script": script,
            "args": args
        }
        return self.send_command("POST", "execute/async", body)

    #[...]

    @command
    def screenshot(self):
        return self.send_command("GET", "screenshot")


class Element(object):
    def __init__(self, session, id):
        self.session = session
        self.id = id
        assert id not in self.session._element_cache
        self.session._element_cache[self.id] = self

    def json(self):
        return {element_key: self.id}

    @property
    def session_id(self):
        return self.session.session_id

    def url(self, suffix):
        return "element/%s/%s" % (self.id, suffix)

    @command
    def find_element(self, strategy, selector):
        body = {"using": strategy,
                "value": selector}

        elem = self.session.send_command("POST", self.url("element"), body)
        return self.session.element(elem)

    @command
    def click(self):
        self.session.send_command("POST", self.url("click"), {})

    @command
    def tap(self):
        self.session.send_command("POST", self.url("tap"), {})

    @command
    def clear(self):
        self.session.send_command("POST", self.url("clear"), {})

    @command
    def send_keys(self, keys):
        if isinstance(keys, (str, unicode)):
            keys = [char for char in keys]

        body = {"value": keys}

        return self.session.send_command("POST", self.url("value"), body)

    @property
    @command
    def text(self):
        return self.session.send_command("GET", self.url("text"))

    @property
    @command
    def name(self):
        return self.session.send_command("GET", self.url("name"))

    @command
    def style(self, property_name):
        return self.session.send_command("GET", self.url("css/%s" % property_name))

    @property
    @command
    def rect(self):
        return self.session.send_command("GET", self.url("rect"))

    @command
    def property(self, name):
        return self.session.send_command("GET", self.url("property/%s" % name))

    @command
    def attribute(self, name):
        return self.session.send_command("GET", self.url("attribute/%s" % name))
