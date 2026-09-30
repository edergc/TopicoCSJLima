"""Importa todos los modelos ORM para que SQLAlchemy resuelva las relaciones entre módulos."""

from app.modules.appointments import models as appointments_models  # noqa: F401
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.imports import models as imports_models  # noqa: F401
from app.modules.notifications import models as notifications_models  # noqa: F401
from app.modules.sites import models as sites_models  # noqa: F401
from app.modules.users import models as users_models  # noqa: F401
from app.modules.workers import models as workers_models  # noqa: F401
