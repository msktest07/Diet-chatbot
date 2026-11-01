import streamlit as st

from chatbot import LOG_FILE, MODEL, PROMPTS, ask, log_interaction, new_run_id

st.set_page_config(page_title="Diet Chatbot", page_icon="🥗")
st.title("Diet Chatbot")
st.caption("Ask me about diet, nutrition, and healthy eating.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "run_id" not in st.session_state:
    st.session_state.run_id = new_run_id("ui")

with st.sidebar:
    st.header("Tester panel")
    versions = list(PROMPTS)
    prompt_version = st.selectbox("Prompt version", versions, index=versions.index("v2"),
                                  help="v1 is the original prompt; v2 adds the rules found missing in the first evaluation.")
    case_id = st.text_input("Test case ID (optional)", placeholder="e.g. D09",
                            help="Logged with the question so each answer can be traced to a golden.")
    show_stats = st.checkbox("Show latency and tokens", value=True)
    st.caption(f"Model: {MODEL} · Session: {st.session_state.run_id}")
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()
    if LOG_FILE.exists():
        st.download_button("Download chat log (CSV)", LOG_FILE.read_bytes(), file_name="chat_log.csv", mime="text/csv")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("stats") and show_stats:
            st.caption(message["stats"])

question = st.chat_input("Ask a diet or nutrition question...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = ask(question, prompt_version)
        st.markdown(reply.answer)
        stats = (f"prompt {reply.prompt_version} · {reply.latency_ms} ms · "
                 f"{reply.input_tokens} + {reply.output_tokens} tokens · ${reply.cost_usd:.5f}"
                 + (f" · case {case_id}" if case_id else ""))
        if show_stats:
            st.caption(stats)
    log_interaction(question, reply, source="ui", run_id=st.session_state.run_id, case_id=case_id.strip())
    st.session_state.messages.append({"role": "assistant", "content": reply.answer, "stats": stats})
