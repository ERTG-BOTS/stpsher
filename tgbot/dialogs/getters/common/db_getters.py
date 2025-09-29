from infrastructure.database.models import Employee
from infrastructure.database.repo.KPI.requests import KPIRequestsRepo
from infrastructure.database.repo.STP.requests import MainRequestsRepo


async def db_getter(**kwargs):
    user: Employee = kwargs.get("user")
    stp_repo: MainRequestsRepo = kwargs.get("stp_repo")
    kpi_repo: KPIRequestsRepo = kwargs.get("kpi_repo")

    return {"user": user, "stp_repo": stp_repo, "kpi_repo": kpi_repo}
