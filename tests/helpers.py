import re

from django.test import RequestFactory
from tri_declarative import (
    declarative,
    dispatch,
    Namespace,
    Refinable,
)
from tri_struct import Struct

from iommi import (
    Table,
    middleware,
)
from iommi.base import items
from iommi.member import (
    bind_members,
    refine_done_members,
)
from iommi.refinable import RefinableMembers
from iommi.traversable import (
    Traversable,
)


def reindent(s, before=" ", after="    "):

    def reindent_line(line):
        m = re.match(r'^((' + re.escape(before) + r')*)(.*)', line)
        return after * (len(m.group(1)) // len(before)) + m.group(3)

    return "\n".join(reindent_line(line) for line in s.splitlines())


def remove_csrf(html_code):
    csrf_regex = r'<input[^>]+csrfmiddlewaretoken[^>]+>'
    return re.sub(csrf_regex, '', html_code)


@dispatch(
    table__call_target=Table,
)
def verify_table_html(*, expected_html, query=None, find=None, table, **kwargs):
    """
    Verify that the table renders to the expected markup, modulo formatting
    """
    from bs4 import BeautifulSoup
    if find is None:
        find = dict(class_='table')
        if not expected_html.strip():
            expected_html = "<table/>"  # pragma: no cover

    if isinstance(table, Namespace):
        table = table()

    table: Table

    request = RequestFactory().get("/", query)
    if not table._is_bound:
        table = table.bind(request=request)

    from django.contrib.auth.models import AnonymousUser
    request.user = AnonymousUser()
    actual_html = remove_csrf(table.__html__(**kwargs))

    expected_soup = BeautifulSoup(expected_html, 'html.parser')
    prettified_expected = reindent(expected_soup.find(**find).prettify()).strip()
    actual_soup = BeautifulSoup(actual_html, 'html.parser')
    hit = actual_soup.find(**find)
    if not hit:  # pragma: no cover
        print(actual_html)
        assert False, f"Couldn't find selector {find} in actual output"
    assert hit, actual_soup
    prettified_actual = reindent(hit.prettify()).strip()

    if prettified_actual != prettified_expected:  # pragma: no cover
        print(actual_html)
    assert prettified_actual == prettified_expected


def request_with_middleware(response, request):
    def get_response(request):
        del request
        return response

    m = middleware(get_response)
    return m(request=request)


def no_auth_middleware_req(method, **data):
    return getattr(RequestFactory(HTTP_REFERER='/'), method.lower())('/', data=data)


def req(method, **data):
    request = no_auth_middleware_req(method, **data)
    request.user = Struct(is_staff=False, is_authenticated=False)
    return request


def user_req(method, **data):
    request = req(method, **data)
    request.user = Struct(is_staff=False, is_authenticated=True)
    return request


def staff_req(method, **data):
    request = req(method, **data)
    request.user = Struct(is_staff=True, is_authenticated=True)
    return request


def get_attrs(x, attrs):
    return {a: x.attrs.get(a) for a in attrs}


class StubTraversable(Traversable):
    def __init__(self, *, _name, members=None):
        super(StubTraversable, self).__init__(_name=_name)
        self._declared_members = members or {}

    def on_bind(self):
        self._bound_members = Struct({k: v.bind(parent=self) for k, v in items(self._declared_members)})


class Fruit(Traversable):
    taste = Refinable()


@declarative(Fruit, 'fruits_dict', add_init_kwargs=False)
class Basket(Traversable):
    fruits: Namespace = RefinableMembers()

    def __init__(self, unknown_types_fall_through=False, **kwargs):
        self.unknown_types_fall_through = unknown_types_fall_through
        super(Basket, self).__init__(**kwargs)

    def on_refine_done(self):
        refine_done_members(container=self, name='fruits', members_from_namespace=self.fruits, members_from_declared=self.get_declared('fruits_dict'), cls=Fruit, unknown_types_fall_through=self.unknown_types_fall_through)
        super(Basket, self).on_refine_done()

    def on_bind(self):
        bind_members(container=self, name='fruits')


@declarative(Traversable, 'items_dict', add_init_kwargs=False)
class Box(Traversable):
    items: Namespace = RefinableMembers()

    def __init__(self, unknown_types_fall_through=False, **kwargs):
        self.unknown_types_fall_through = unknown_types_fall_through
        super(Box, self).__init__(**kwargs)

    def on_refine_done(self):
        refine_done_members(container=self, name='items', members_from_namespace=self.items, members_from_declared=self.get_declared('items_dict'), cls=Basket, unknown_types_fall_through=self.unknown_types_fall_through)
        super(Box, self).on_refine_done()

    def on_bind(self):
        bind_members(container=self, name='items')


def prettify(content):
    from bs4 import BeautifulSoup
    return reindent(BeautifulSoup(content, 'html.parser').prettify().strip())
