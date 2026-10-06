"""Contrato de los reportes agregados (sin datos personales)."""

from datetime import date

from app.shared.schemas import ApiOut


class ReportTotalsOut(ApiOut):
    capacity: int
    requested: int
    attended: int
    cancelled: int
    no_show: int
    voided: int
    pending: int
    utilization_pct: float | None
    no_show_pct: float | None
    avg_wait_minutes: float | None
    avg_service_minutes: float | None


class ReportDayOut(ApiOut):
    service_date: date
    site_id: int
    site_name: str
    capacity: int
    requested: int
    attended: int
    cancelled: int
    no_show: int
    voided: int


class ReportHourOut(ApiOut):
    hour: int
    count: int


class ReportDepartmentOut(ApiOut):
    department: str
    count: int


class ReportChannelOut(ApiOut):
    channel: str
    count: int


class ReportDoctorOut(ApiOut):
    doctor: str
    attended: int
    avg_service_minutes: float | None


class RatingBucketOut(ApiOut):
    score: int
    count: int


class RatingCommentOut(ApiOut):
    service_date: date
    site_name: str
    score: int
    comment: str


class RatingSummaryOut(ApiOut):
    invited: int
    count: int
    avg_score: float | None
    avg_wait_score: float | None
    distribution: list[RatingBucketOut]
    comments: list[RatingCommentOut]


class ReportSummaryOut(ApiOut):
    date_from: date
    date_to: date
    site_ids: list[int]
    totals: ReportTotalsOut
    by_day: list[ReportDayOut]
    by_hour: list[ReportHourOut]
    by_department: list[ReportDepartmentOut]
    by_channel: list[ReportChannelOut]
    by_doctor: list[ReportDoctorOut]
    rating: RatingSummaryOut
