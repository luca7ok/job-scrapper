from . import (
    adzuna,
    arbeitnow,
    ashby,
    earlycareers_eu,
    greenhouse,
    lever,
    manual,
    simplify,
    smartrecruiters,
    speedyapply,
    workable,
    workday,
)

ATS = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "workable": workable,
    "smartrecruiters": smartrecruiters,
    "workday": workday,
}

LISTS = {
    "simplify_intern": simplify,
    "simplify_newgrad": simplify,
    "speedyapply_intern": speedyapply,
    "speedyapply_newgrad": speedyapply,
    "earlycareers": earlycareers_eu,
}

AGGREGATORS = {
    "arbeitnow": arbeitnow,
    "adzuna": adzuna,
}

__all__ = ["ATS", "LISTS", "AGGREGATORS", "manual"]
