"""Explicit, whitelisted source-page restoration; never restore plot/event state."""
from copy import deepcopy
import streamlit as st

OVERVIEW="pages/01_产业技术全景.py"
SUBJECTS="pages/02_创新主体与合作网络.py"
QA="pages/03_智能问答与关联路径.py"
_KEYS={OVERVIEW:["ov_years","ov_countries","ov_domains","ov_dimension","ov_topic","ov_topic_query","ov_topic_subject","ov_qa_action"],
       SUBJECTS:["org_query","org_scope","org_selected","org_qa_action","org_partner","org_metric","org_top_n","org_coop_subject","org_evidence_view"]}
for page,prefixes in [(OVERVIEW,["ov_patents"]),(SUBJECTS,["org_patents","org_shared"])]:
    _KEYS[page].extend(f"{prefix}_{suffix}" for prefix in prefixes for suffix in ["query","size","page","detail","qa_subject"])


def capture_source(page):
    if page not in _KEYS:return None
    return {"page":page,"values":{k:deepcopy(st.session_state[k]) for k in _KEYS[page] if k in st.session_state}}


def restore_source(page):
    snapshot=st.session_state.get("ev_restore_origin")
    if not snapshot or snapshot.get("page")!=page:return
    for key,value in snapshot.get("values",{}).items():
        if key in _KEYS[page]:st.session_state[key]=deepcopy(value)
    st.session_state.pop("ev_restore_origin",None)


def return_link(origin,*,key):
    if not isinstance(origin,dict) or origin.get("page") not in _KEYS:return
    label="产业技术全景" if origin["page"]==OVERVIEW else "创新主体与合作网络"
    if st.button(f"返回来源页面：{label}",key=key):
        st.session_state["ev_restore_origin"]=deepcopy(origin)
        st.switch_page(origin["page"])


def subject_link(name,*,merged):
    if st.button("查看该主体的技术布局",key="ov_open_subject"):
        st.session_state["org_overview_origin"]=capture_source(OVERVIEW)
        st.session_state["org_pending_partner"]=name
        st.session_state["org_metric"]="patent_count"
        st.session_state["org_scope"]="confirmed" if merged else "raw"
        st.switch_page(SUBJECTS)
