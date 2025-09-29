from aiogram.fsm.state import State, StatesGroup


class HeadSG(StatesGroup):
    menu = State()
    kpi = State()
    kpi_requirements = State()
    salary = State()
    my_group = State()
    products_activation = State()
    game = State()
    search = State()
    groups = State()
    settings = State()
    schedule = State()
    schedule_my = State()
    schedule_my_detailed = State()
    schedule_group = State()
    schedule_duties = State()
    schedule_heads = State()
