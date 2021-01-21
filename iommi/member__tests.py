import pytest
from tri_declarative import (
    class_shortcut,
    dispatch,
    Refinable,
)

from iommi import (
    Fragment,
    html,
    Page,
    register_style,
    Style,
)
from iommi.member import ForbiddenNamesException
from iommi.traversable import (
    declared_members,
)
from tests.helpers import (
    Basket,
    Fruit,
)


def test_empty_collect():
    assert declared_members(Basket().refine_done()).fruits == {}


def test_collect_from_arg():
    basket = Basket(fruits__banana__taste="sweet").refine_done()
    assert declared_members(basket).fruits.banana.taste == 'sweet'


def test_collect_from_declarative():
    class MyBasket(Basket):
        orange = Fruit(taste='sour')

    basket = MyBasket().refine_done()
    assert declared_members(basket).fruits.orange.taste == 'sour'


def test_collect_from_both():
    class MyBasket(Basket):
        orange = Fruit(taste='sour')

    basket = MyBasket(fruits__banana__taste="sweet").refine_done()
    assert declared_members(basket).fruits.banana.taste == 'sweet'
    assert declared_members(basket).fruits.orange.taste == 'sour'


def test_collect_unapplied_config():
    class MyBasket(Basket):
        pear = Fruit()

    basket = MyBasket(fruits__pear__taste='meh').refine_done()
    # noinspection PyUnresolvedReferences
    assert basket.namespace.fruits.pear.taste == 'meh'


def test_unbound_error():
    class MyBasket(Basket):
        orange = Fruit(taste='sour')

    basket = MyBasket().refine_done()
    assert basket.fruits is None


def test_empty_bind():
    basket = Basket().bind()
    assert basket.fruits == {}


def test_bind_from_arg():
    basket = Basket(fruits__banana__taste="sweet").bind()
    assert basket.fruits.banana.taste == 'sweet'


def test_bind_from_declarative():
    class MyBasket(Basket):
        orange = Fruit(taste='sour')

    basket = MyBasket().bind()
    assert basket.fruits.orange.taste == 'sour'


def test_bind_via_unapplied_config():
    class MyBasket(Basket):
        pear = Fruit()

    basket = MyBasket(fruits__pear__taste='meh').bind()
    assert basket.fruits.pear.taste == 'meh'

    with pytest.raises(TypeError) as e:
        MyBasket(fruits__pear__color='green').bind()

    assert (
        str(e.value)
        == "'Fruit' object has no refinable attribute(s): \"color\".\nAvailable attributes:\n    assets\n    endpoints\n    iommi_style\n    taste\n"
    )


def test_ordering():
    class OrderFruit(Fruit):
        after = Refinable()

    class MyBasket(Basket):
        banana = OrderFruit()
        pear = OrderFruit()
        orange = OrderFruit()

    basket = MyBasket(
        fruits__orange__after=0,
        fruits__banana__after='pear',
    ).bind()

    assert list(basket.fruits.keys()) == ['orange', 'pear', 'banana']
    assert basket._bound_members['fruits']._bound_members is basket.fruits


def test_inclusion():
    class IncludableFruit(Fruit):
        include = Refinable()

        @dispatch(include=True)
        def __init__(self, **kwargs):
            super(IncludableFruit, self).__init__(**kwargs)

    class MyBasket(Basket):
        banana = IncludableFruit()
        pear = IncludableFruit()
        orange = IncludableFruit(include=False)

    basket = MyBasket(
        fruits__banana__include=False,
    ).bind()

    assert list(basket.fruits.keys()) == ['pear']


def test_unapplied_config_does_not_remember_simple():
    from iommi import Page
    from iommi import html

    class MyPage(Page):
        link = html.a('Admin')

    a = MyPage(parts__link__attrs__href='#foo#').bind()
    b = MyPage().bind()
    assert '#foo#' in a.__html__()
    assert '#foo#' not in b.__html__()


def test_override_grandchild():
    class MyPage(Page):
        foo = Fragment(Fragment('bar'), tag='h1')

    assert MyPage(parts__foo__children__text__tag='span').bind().__html__() == '<h1><span>bar</span></h1>'


def test_unapplied_config_does_not_remember():
    from iommi import Page
    from iommi import html

    class MyPage(Page):
        header = html.h1(children__link=html.a('Admin'))

    a = MyPage(parts__header__children__link__attrs__href='#foo#').bind()
    b = MyPage().bind()
    assert '#foo#' in a.__html__()
    assert '#foo#' not in b.__html__()


@pytest.fixture
def foo_style():
    with register_style('precedence', Style(Page__parts__foo=html.div('from style'))):
        yield


def test_precedence(foo_style):
    class MyPage(Page):
        class Meta:
            iommi_style = 'precedence'

    assert str(MyPage().bind()) == '<div>from style</div>'


def test_precedence_override_style(foo_style):
    class MyPage(Page):
        foo = html.div('from declaration')

        class Meta:
            iommi_style = 'precedence'

    assert str(MyPage().bind()) == '<div>from declaration</div>'
    assert (
        str(MyPage.shortcut(parts__foo=html.div('from constructor call')).bind()) == '<div>from constructor call</div>'
    )


def test_precedence_override_meta(foo_style):
    class MyPage(Page):
        foo = html.div('from declaration')

        class Meta:
            iommi_style = 'precedence'
            parts__foo = html.div('from class Meta')

    assert str(MyPage().bind()) == '<div>from class Meta</div>'
    assert str(MyPage(parts__foo=html.div('from constructor call')).bind()) == '<div>from constructor call</div>'


def test_precedence_override_shortcut(foo_style):
    class MyPage(Page):
        foo = html.div('from declaration')

        class Meta:
            iommi_style = 'precedence'

        @classmethod
        @class_shortcut(parts__foo=html.div('from shortcut'))
        def shortcut(cls, call_target, **kwargs):
            return call_target(**kwargs)

    assert str(MyPage.shortcut().bind()) == '<div>from shortcut</div>'

    assert (
        str(MyPage.shortcut(parts__foo=html.div('from constructor call')).bind()) == '<div>from constructor call</div>'
    )


def test_lazy_bind():
    class ExplodingFruit(Fruit):
        def on_bind(self):
            raise Exception('Boom')

    class MyBasket(Basket):
        tasty_banana = Fruit(taste='sweet')
        exploding_orange = ExplodingFruit(taste='strange')

    my_basket = MyBasket().bind()
    assert my_basket.fruits.tasty_banana.taste == 'sweet'

    with pytest.raises(Exception) as e:
        # noinspection PyStatementEffect
        my_basket.fruits.exploding_orange
    assert 'Boom' in str(e.value)


def test_lazy_repr():
    class MyBasket(Basket):
        banana = Fruit(taste='sweet')
        orange = Fruit(taste='strange')

    my_basket = MyBasket().bind()
    # noinspection PyStatementEffect
    my_basket.fruits.banana
    assert repr(my_basket.fruits) == '<MemberBinder: banana (bound), orange>'
    assert str(my_basket.fruits) == '<MemberBinder: banana (bound), orange>'


def test_forbidden_names():
    class MyBasket(Basket):
        _name = Fruit()
        iommi_style = Fruit()

    with pytest.raises(ForbiddenNamesException) as e:
        MyBasket().refine_done()

    assert str(e.value) == 'The names _name, iommi_style are reserved by iommi, please pick other names'


def test_collect_sets_name():
    class MyBasket(Basket):
        orange = Fruit(taste='sour')

    basket = MyBasket().refine_done()
    assert declared_members(basket).fruits.orange._name == 'orange'

    basket = MyBasket(fruits__orange=Fruit(taste='sour')).refine_done()
    assert declared_members(basket).fruits.orange._name == 'orange'


def test_none_members_should_be_discarded_after_being_allowed_through():
    class MyBasket(Basket):
        orange = Fruit(taste='sour')

    basket = MyBasket(fruits__orange=None).refine_done()
    assert 'orange' not in declared_members(basket).fruits


def test_bind_not_reorder():
    class MyBasket(Basket):
        banana = Fruit(taste='sweet')
        orange = Fruit(taste='strange')

    my_basket = MyBasket().bind()
    # noinspection PyStatementEffect
    my_basket.fruits.orange
    assert list(my_basket.fruits.keys()) == ['banana', 'orange']
