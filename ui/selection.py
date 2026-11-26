"""Validate rank-chart selections against the actual rendered records."""
def selected_rank_name(event,names):
    points=(event or {}).get("selection",{}).get("points",[])
    if not points:return None
    custom=points[-1].get("customdata",[])
    name=custom[0] if isinstance(custom,(list,tuple)) and custom else None
    return name if isinstance(name,str) and name in names else None
