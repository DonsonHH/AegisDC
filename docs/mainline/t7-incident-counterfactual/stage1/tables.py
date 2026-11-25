"""Paired descriptive tables over saved T3 and T7 returns."""

from statistics import mean


ROLES = ("P", "ORACLE", "PERIODIC", "ALARM")
ROSTER = [f"{family}-{draw:02}" for draw in range(1, 13) for family in (5, 6)]


def describe(saved_t3, returns):
    baseline = {row["key"]: row for row in saved_t3["rows"]}
    table = []
    for key in ROSTER:
        old = baseline[key]
        arms = {role: {metric: old["arms"][role][metric] for metric in ("L", "person")} for role in ROLES}
        actual = returns.get(key)
        if actual is not None:
            if any(old["arms"][role]["input_sha256"] != actual["input_sha256"] for role in ROLES):
                raise ValueError("different original condition: " + key)
            arms["V_COST"] = {metric: actual[metric] for metric in ("L", "person")}
        else:
            arms["V_COST"] = None
        table.append({"key": key, "family": old["family"], "arms": arms})
    families = {}
    for family in ("LONDON", "NETHERLANDS"):
        all_rows = [r["arms"] for r in table if r["family"] == family]
        pairs = [row for row in all_rows if row["V_COST"] is not None]
        comparisons = {}
        for role in ROLES:
            stats = {}
            for metric in ("L", "person"):
                delta = [row["V_COST"][metric] - row[role][metric] for row in pairs]
                tolerance = 1e-7 if metric == "L" else 0
                stats[metric] = {"method_mean": mean(r["V_COST"][metric] for r in pairs) if pairs else None,
                                 "comparator_mean": mean(r[role][metric] for r in pairs) if pairs else None,
                                 "paired_mean_difference": mean(delta) if pairs else None,
                                 "better_equal_worse": [sum(d < -tolerance for d in delta),
                                                        sum(abs(d) <= tolerance for d in delta),
                                                        sum(d > tolerance for d in delta)]}
            comparisons[role] = stats
        families[family] = {"planned": len(all_rows), "paired": len(pairs), "comparisons": comparisons}
    return {"rows": table, "families": families}
