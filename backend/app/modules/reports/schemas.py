"""Contrato de los reportes agregados (sin datos personales)."""

from datetime import date, datetime

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


class SatisfactionGroupOut(ApiOut):
    count: int
    avg_score: float | None
    avg_wait_score: float | None


class SatisfactionMonthOut(SatisfactionGroupOut):
    month: str


class SatisfactionSiteOut(SatisfactionGroupOut):
    site_name: str


class SatisfactionDoctorOut(SatisfactionGroupOut):
    doctor: str


class SatisfactionCommentOut(ApiOut):
    service_date: date
    submitted_at: datetime
    site_name: str
    doctor: str | None
    score: int
    wait_score: int | None
    comment: str


class SatisfactionReportOut(ApiOut):
    date_from: date
    date_to: date
    invited: int
    count: int
    response_pct: float | None
    with_comment: int
    avg_score: float | None
    avg_wait_score: float | None
    distribution: list[RatingBucketOut]
    wait_distribution: list[RatingBucketOut]
    by_month: list[SatisfactionMonthOut]
    by_site: list[SatisfactionSiteOut]
    by_doctor: list[SatisfactionDoctorOut]
    comments_total: int
    page: int
    page_size: int
    comments: list[SatisfactionCommentOut]
