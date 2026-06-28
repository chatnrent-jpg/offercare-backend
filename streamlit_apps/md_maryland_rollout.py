"""VettedCare.ai — Maryland LTC rollout monitoring dashboard (Streamlit)."""



from __future__ import annotations



import csv

from pathlib import Path



import pandas as pd

import streamlit as st



REPO_ROOT = Path(__file__).resolve().parents[1]

CSV_PATH = REPO_ROOT / "data_engine" / "raw_leads" / "md_facilities_scraped.csv"



st.set_page_config(

    page_title="VettedCare.ai — Maryland Rollout",

    page_icon="🏥",

    layout="wide",

    initial_sidebar_state="expanded",

)



DARK_CSS = """

<style>

    .stApp { background-color: #09090b; color: #e4e4e7; }

    [data-testid="stMetric"] {

        background: #18181b; border: 1px solid #27272a; border-radius: 8px; padding: 12px;

    }

    [data-testid="stMetricLabel"] { color: #a1a1aa !important; font-size: 0.8rem; }

    [data-testid="stMetricValue"] { color: #fafafa !important; }

    .snf-alert {

        background: #451a03; border: 1px solid #ea580c; border-radius: 8px;

        padding: 12px 16px; margin: 8px 0; color: #fed7aa;

    }

    .sys-chip {

        display: inline-block; background: #14532d; color: #bbf7d0;

        border-radius: 999px; padding: 4px 12px; font-size: 0.75rem;

        font-family: monospace; margin-bottom: 12px;

    }

    h1, h2, h3 { color: #fafafa !important; }

    .stDataFrame { border: 1px solid #27272a; border-radius: 8px; }

</style>

"""

st.markdown(DARK_CSS, unsafe_allow_html=True)





def _table_exists(db, table_name: str) -> bool:

    from sqlalchemy import inspect



    return table_name in inspect(db.get_bind()).get_table_names()





@st.cache_data(ttl=60)

def load_facilities_from_csv() -> pd.DataFrame:

    if not CSV_PATH.is_file():

        return pd.DataFrame(

            columns=[

                "facility_name",

                "facility_type",

                "md_license_number",

                "county",

                "contact_name",

                "contact_role",

                "contact_email",

            ]

        )

    with CSV_PATH.open(newline="", encoding="utf-8-sig") as handle:

        return pd.DataFrame(list(csv.DictReader(handle)))





@st.cache_data(ttl=60)

def load_facilities_from_db() -> tuple[pd.DataFrame, str]:

    try:

        from app.database import SessionLocal

        from data_engine.md_facility_import import list_facilities_with_contacts



        db = SessionLocal()

        try:

            if not _table_exists(db, "facilities"):

                return pd.DataFrame(), "csv"

            rows = list_facilities_with_contacts(db, limit=500)

            if not rows:

                return pd.DataFrame(), "csv"

            return pd.DataFrame(rows), "postgres"

        finally:

            db.close()

    except Exception:

        return pd.DataFrame(), "csv"





def load_facilities() -> tuple[pd.DataFrame, str]:

    db_df, source = load_facilities_from_db()

    if source == "postgres" and not db_df.empty:

        return db_df, source

    return load_facilities_from_csv(), "csv"





@st.cache_data(ttl=60)

def load_provider_metrics() -> dict[str, int | bool]:

    """Best-effort live counts from PostgreSQL; falls back to prototype values."""

    try:

        from app.database import SessionLocal

        from app.models import MdFacilityContact, MarylandProvider, MdOutreachPayload

        from sqlalchemy import func



        db = SessionLocal()

        try:

            compliant = (

                db.query(func.count(MarylandProvider.provider_id))

                .filter(

                    MarylandProvider.state == "MD",

                    MarylandProvider.credential_type.in_(["CNA", "GNA", "LPN"]),

                    MarylandProvider.license_status == "VERIFIED",

                )

                .scalar()

                or 0

            )

            outreach_pending = 0

            if _table_exists(db, "facility_contacts"):

                outreach_pending = (

                    db.query(func.count(MdFacilityContact.contact_id))

                    .filter(MdFacilityContact.outreach_status == "READY")

                    .scalar()

                    or 0

                )

            elif _table_exists(db, "md_outreach_payloads"):

                outreach_pending = (

                    db.query(func.count(MdOutreachPayload.payload_id))

                    .filter(MdOutreachPayload.status == "READY")

                    .scalar()

                    or 0

                )

            return {

                "compliant_providers": int(compliant),

                "outreach_pending": int(outreach_pending),

                "db_connected": True,

            }

        finally:

            db.close()

    except Exception:

        return {"compliant_providers": 0, "outreach_pending": 0, "db_connected": False}





def main() -> None:

    df, data_source = load_facilities()

    metrics = load_provider_metrics()



    st.markdown('<span class="sys-chip">SYS_STATUS · MD_LTC_ROLLOUT · LIVE</span>', unsafe_allow_html=True)

    st.title("Maryland Market Rollout — Operations Console")

    st.caption(

        "Manus lead sourcing · OHCQ/MHCC facility registry · MBON compliance gate · B2B outreach sequencer"

    )



    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Loaded Facilities", len(df))

    col2.metric("SNF Targets", int((df["facility_type"] == "SNF").sum()) if not df.empty else 0)

    col3.metric(

        "Active Compliant Providers (CNA/GNA/LPN)",

        metrics["compliant_providers"],

        help="Live count from maryland_providers when DB is reachable",

    )

    col4.metric(

        "Pending Outreach Campaigns",

        metrics["outreach_pending"] or int((df["facility_type"].notna()).sum() if not df.empty else 0),

        help="READY rows in facility_contacts (or md_outreach_payloads), else facility row count",

    )



    if not metrics["db_connected"]:

        st.info("Database not connected — provider/outreach metrics show fallback values. Start API + Postgres for live counts.")



    st.subheader("Maryland B2B Facility Leads")

    if data_source == "postgres":

        st.caption("Source: PostgreSQL `facilities` + `facility_contacts` (imported from scraped CSV)")

    else:

        st.caption(f"Source file: `{CSV_PATH}` (run `scripts/import_md_facilities_scraped.py` to load into Postgres)")



    if df.empty:

        st.warning("No scraped facilities found. Drop `md_facilities_scraped.csv` into data_engine/raw_leads/.")

        return



    display = df.copy()

    display["compliance_alert"] = display["facility_type"].apply(

        lambda ft: "⚠ SNF GNA rule" if str(ft).upper() == "SNF" else ""

    )

    st.dataframe(display, use_container_width=True, hide_index=True)



    snf_rows = df[df["facility_type"].str.upper() == "SNF"]

    if not snf_rows.empty:

        st.subheader("SNF Compliance Alerts")

        for _, row in snf_rows.iterrows():

            name = row.get("facility_name") or row.get("company_name", "Unknown")

            county = row.get("county") or row.get("md_county", "")

            st.markdown(

                f'<div class="snf-alert"><strong>{name}</strong> ({county}) — '

                "Strict Compliance Rule Active: CNAs placed here require a verified GNA endorsement.</div>",

                unsafe_allow_html=True,

            )



    with st.expander("Schema alignment (003_maryland_market.sql)"):

        st.markdown(

            """

            - **facilities** · `facility_type_enum` SNF / ALF / HHA

            - **facility_contacts** · ADMINISTRATOR / DON / HR_HEAD + `outreach_status_enum`

            - **md_provider_compliance** · `has_gna_endorsement` + county index for lookahead matching

            """

        )





if __name__ == "__main__":

    main()

