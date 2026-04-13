from pathlib import Path
import mimetypes

import streamlit as st
import requests

API_URL = "http://localhost:8000"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(page_title="Coffee Vision Dashboard", layout="wide")


def _resolve_file_path(file_path):
    """Convert relative path to absolute for Streamlit compatibility."""
    if not file_path:
        return None
    p = Path(file_path)
    candidates = []
    if p.is_absolute():
        candidates.append(p)
    else:
        candidates.append(PROJECT_ROOT / p)
        candidates.append(Path.cwd() / p)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())

    return None


def _video_mime_type(file_path):
    guessed, _ = mimetypes.guess_type(str(file_path))
    if guessed and guessed.startswith("video/"):
        return guessed
    return "video/mp4"


def _decode_fourcc(value):
    try:
        int_value = int(value)
    except (TypeError, ValueError):
        return None
    if int_value <= 0:
        return None

    chars = [chr((int_value >> (8 * i)) & 0xFF) for i in range(4)]
    code = "".join(chars).strip()
    if len(code) != 4:
        return None
    if any((ord(c) < 32 or ord(c) > 126) for c in code):
        return None
    return code


def _inspect_video_file(file_path):
    path = Path(file_path)
    suffix = path.suffix.lower()
    mime_type = _video_mime_type(path)
    codec = None

    try:
        import cv2

        cap = cv2.VideoCapture(str(path))
        try:
            codec = _decode_fourcc(cap.get(cv2.CAP_PROP_FOURCC))
        finally:
            cap.release()
    except Exception:
        codec = None

    return {
        "container": suffix or "(none)",
        "mime_type": mime_type,
        "codec": codec or "unknown",
    }


def _bound_boxes_browser_warning(file_path):
    details = _inspect_video_file(file_path)
    suffix = details["container"]
    codec = details["codec"]

    if suffix not in {".mp4", ".webm", ".ogg"}:
        return (
            f"Bound-boxes video uses '{suffix or 'no extension'}' container, which may not play in all browsers. "
            "Prefer .mp4 (H.264/AVC) for widest compatibility."
        )

    if suffix == ".mp4":
        compatible_mp4_codecs = {"avc1", "h264", "x264"}
        if codec != "unknown" and codec.lower() not in compatible_mp4_codecs:
            return (
                f"Bound-boxes video codec appears to be '{codec}' in MP4 container. "
                "Some browsers may fail to decode it. Prefer H.264/AVC ('avc1')."
            )

    return None


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


def reprocess_video(video_id, api_url=API_URL):
    try:
        response = requests.post(f"{api_url}/videos/{video_id}/reprocess", timeout=240)
    except requests.RequestException as exc:
        return False, f"API unavailable: {exc}"

    if response.ok:
        return True, "Video reprocessed"

    try:
        detail = response.json().get("detail", "Reprocess failed")
    except ValueError:
        detail = response.text or "Reprocess failed"

    return False, f"Reprocess rejected: {detail}"


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


def resolve_video_path(video, show_bound_boxes=False):
    """Resolve video path with validation, preferring bound_boxes if requested."""
    if show_bound_boxes:
        bbox_path = _resolve_file_path(video.get("bound_boxes_file_path"))
        if bbox_path:
            return bbox_path
        return None
    else:
        original_path = _resolve_file_path(video.get("file_path"))
        if original_path:
            return original_path
    
    return None

def _load_css(path: Path) -> None:
    with open(path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_dashboard():
    _load_css(Path(__file__).parent / "styles.css")

    st.title("Coffee Vision Dashboard")

    if "last_reprocess_feedback" not in st.session_state:
        st.session_state["last_reprocess_feedback"] = None

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

        if st.session_state["last_reprocess_feedback"]:
            ok, message = st.session_state["last_reprocess_feedback"]
            if ok:
                st.success(message)
            else:
                st.error(message)
            st.session_state["last_reprocess_feedback"] = None

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
            show_bound_boxes = st.checkbox("Show bound boxes", value=False, key="viewer_show_bound_boxes")

            video_path = resolve_video_path(selected_video, show_bound_boxes=show_bound_boxes)
            
            if video_path:
                try:
                    st.video(video_path, format=_video_mime_type(video_path))
                except Exception as e:
                    st.error(f"Error loading video: {e}")
                else:
                    details = _inspect_video_file(video_path)
                    diagnostics_label = "Bound-boxes" if show_bound_boxes else "Original"
                    st.caption(
                        f"{diagnostics_label} diagnostics: "
                        f"container={details['container']} | "
                        f"mime={details['mime_type']} | "
                        f"codec={details['codec']}"
                    )

                    if show_bound_boxes:
                        browser_warning = _bound_boxes_browser_warning(video_path)
                        if browser_warning:
                            st.warning(browser_warning)
            else:
                requested_type = "bound boxes" if show_bound_boxes else "original"
                st.warning(f"Could not find {requested_type} video file. Status: {selected_video['status']}")
            
            st.caption(
                f"Camera: {selected_video['camera_id']} | "
                f"Location: {selected_video['location_name']}#{selected_video['sector_number']}"
            )

            if st.button("Reprocess selected video", use_container_width=True):
                ok, message = reprocess_video(selected_video["id"])
                st.session_state["last_reprocess_feedback"] = (ok, message)
                if ok:
                    st.rerun()

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