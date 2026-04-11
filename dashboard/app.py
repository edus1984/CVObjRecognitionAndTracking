import streamlit as st
import requests

API_URL = "http://localhost:8000"


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
    try:
        response = requests.get(f"{api_url}/videos", timeout=10)
    except requests.RequestException:
        return []

    if not response.ok:
        return []

    try:
        data = response.json()
    except ValueError:
        return []

    return data if isinstance(data, list) else []

def render_dashboard():
    st.title("Coffee Vision Dashboard")

    left_col, right_col = st.columns([4, 1])

    with left_col:
        uploaded = st.file_uploader("Upload video")

        if uploaded:
            ok, message = upload_video_file(uploaded)
            if ok:
                st.success(message)
            else:
                st.error(message)

        st.header("KPIs")
        st.metric("Customers", 10)
        st.metric("Avg Wait", "3 min")

    with right_col:
        st.subheader("Video Viewer")
        videos = fetch_uploaded_videos()

        if videos:
            labels = [f"{video['original_filename']} ({video['status']})" for video in videos]
            selected_label = st.selectbox("Uploaded videos", labels, index=0)
            selected_video = videos[labels.index(selected_label)]

            st.video(selected_video["file_path"])
            st.caption(
                f"Camera: {selected_video['camera_id']} | "
                f"Location: {selected_video['location_name']}#{selected_video['sector_number']}"
            )

            st.divider()
            st.subheader("Uploaded List")
            for video in videos:
                st.write(
                    f"- {video['original_filename']} | events={video['events_count']} | status={video['status']}"
                )
        else:
            st.info("No uploaded videos found in database")


if __name__ == "__main__":
    render_dashboard()