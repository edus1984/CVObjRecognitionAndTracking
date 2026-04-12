from pathlib import Path

import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Coffee Vision Dashboard", layout="wide")


def upload_video_file(uploaded_file, api_url=API_URL):
    files = {"file": uploaded_file}
    try:
        response = requests.post(f"{api_url}/upload", files=files, timeout=120)
    except requests.RequestException as exc:
        return False, f"API unavailable: {exc}"

    if response.ok:
        return True, "Video uploaded and processed"

    try:
        detail = response.json().get("detail", "Upload failed")
    except ValueError:
        detail = response.text or "Upload failed"

    return False, f"Upload rejected: {detail}"


def fetch_uploaded_videos(api_url=API_URL):
    return fetch_uploaded_videos_page(api_url=api_url)


def fetch_uploaded_videos_page(
    api_url=API_URL,
    *,
    skip=0,
    limit=20,
    camera_id=None,
    status=None,
    capture_from=None,
    capture_to=None,
):
    params = {
        "skip": skip,
        "limit": limit,
    }
    if camera_id:
        params["camera_id"] = camera_id
    if status and status != "all":
        params["status"] = status
    if capture_from:
        params["capture_from"] = capture_from
    if capture_to:
        params["capture_to"] = capture_to

    try:
        response = requests.get(f"{api_url}/videos", params=params, timeout=10)
    except requests.RequestException:
        return [], {"skip": skip, "limit": limit, "returned": 0, "total": 0}

    if not response.ok:
        return [], {"skip": skip, "limit": limit, "returned": 0, "total": 0}

    try:
        data = response.json()
    except ValueError:
        return [], {"skip": skip, "limit": limit, "returned": 0, "total": 0}

    if not isinstance(data, dict):
        return [], {"skip": skip, "limit": limit, "returned": 0, "total": 0}

    items = data.get("items", [])
    pagination = data.get("pagination", {"skip": skip, "limit": limit, "returned": 0, "total": 0})

    if not isinstance(items, list):
        items = []

    return items, pagination


def fetch_kpis(api_url=API_URL):
    default = {
        "total_videos": 0,
        "completed_videos": 0,
        "failed_videos": 0,
        "total_events": 0,
        "unique_people": 0,
        "avg_events_per_completed_video": 0.0,
    }

    try:
        response = requests.get(f"{api_url}/kpis", timeout=10)
    except requests.RequestException:
        return default

    if not response.ok:
        return default

    try:
        data = response.json()
    except ValueError:
        return default

    return data if isinstance(data, dict) else default

def _load_css(path: Path) -> None:
    with open(path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_dashboard():
    _load_css(Path(__file__).parent / "styles.css")

    st.title("Coffee Vision Dashboard")

    left_col, right_col = st.columns([3, 1])

    with left_col:
        uploaded = st.file_uploader("Upload video")

        # Streamlit reruns on every widget interaction. Only upload when a new file is selected.
        if "last_uploaded_token" not in st.session_state:
            st.session_state["last_uploaded_token"] = None
        if "last_upload_feedback" not in st.session_state:
            st.session_state["last_upload_feedback"] = None

        if uploaded:
            uploaded_token = f"{uploaded.name}:{uploaded.size}"
            if uploaded_token != st.session_state["last_uploaded_token"]:
                ok, message = upload_video_file(uploaded)
                st.session_state["last_uploaded_token"] = uploaded_token
                st.session_state["last_upload_feedback"] = (ok, message)

            ok, message = st.session_state["last_upload_feedback"]
            if ok:
                st.success(message)
            else:
                st.error(message)
        else:
            st.session_state["last_uploaded_token"] = None
            st.session_state["last_upload_feedback"] = None

        st.header("KPIs")
        kpis = fetch_kpis()
        kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
        kpi_col1.metric("Videos", kpis["total_videos"])
        kpi_col2.metric("Events", kpis["total_events"])
        kpi_col3.metric("Unique People", kpis["unique_people"])
        st.metric("Avg Events / Completed Video", f"{kpis['avg_events_per_completed_video']:.2f}")

    with right_col:
        st.subheader("Video Viewer")

        # Read filter/pagination values from session state (first run uses defaults)
        _camera = st.session_state.get("rcol_camera", "")
        _status = st.session_state.get("rcol_status", "all")
        _page_size = st.session_state.get("rcol_page_size", 10)
        _page_number = st.session_state.get("rcol_page_number", 1)

        skip = (int(_page_number) - 1) * int(_page_size)
        videos, pagination = fetch_uploaded_videos_page(
            skip=skip,
            limit=int(_page_size),
            camera_id=_camera or None,
            status=_status,
        )

        # 1. Video player + selection (before filters)
        if videos:
            labels = [f"{video['original_filename']} ({video['status']})" for video in videos]
            selected_label = st.selectbox("Uploaded videos", labels, index=0)
            selected_video = videos[labels.index(selected_label)]

            st.video(selected_video["file_path"])
            st.caption(
                f"Camera: {selected_video['camera_id']} | "
                f"Location: {selected_video['location_name']}#{selected_video['sector_number']}"
            )

        else:
            st.info("No uploaded videos found in database")

        # 2. Filter and pagination controls
        st.divider()
        fc1, fc2 = st.columns(2)
        fc1.text_input(
            "Camera",
            placeholder="Camera (e.g. C0104)",
            label_visibility="collapsed",
            key="rcol_camera",
        )
        fc2.selectbox(
            "Status",
            ["all", "uploaded", "processing", "completed", "failed"],
            label_visibility="collapsed",
            key="rcol_status",
        )
        pc1, pc2 = st.columns(2)
        pc1.selectbox("Pg size", [5, 10, 20], index=1, label_visibility="collapsed", key="rcol_page_size")
        pc2.number_input("Page", min_value=1, step=1, value=1, label_visibility="collapsed", key="rcol_page_number")

        # 3. Uploaded list
        if videos:
            st.divider()
            st.subheader("Uploaded List")
            for video in videos:
                st.write(
                    f"- {video['original_filename']} | events={video['events_count']} | status={video['status']}"
                )
            st.caption(
                f"Showing {pagination.get('returned', 0)} of {pagination.get('total', 0)} "
                f"(skip={pagination.get('skip', 0)}, limit={pagination.get('limit', _page_size)})"
            )


if __name__ == "__main__":
    render_dashboard()