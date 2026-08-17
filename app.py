import streamlit as st
import hashlib

from rag import (
    load_pdf,
    split_documents,
    create_embeddings,
    create_vector_store,
    create_llm,
    generate_answer,
    rewrite_question
)


st.title("📄 AI Document Assistant")
st.caption("Chat with your PDF using AI-powered semantic search and RAG.")

#CHAT HISTORY 
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "current_pdf_hash" not in st.session_state:
    st.session_state.current_pdf_hash = None
@st.cache_resource
def process_pdf(pdf_bytes, pdf_hash):

    with open("temp.pdf", "wb") as f:
        f.write(pdf_bytes)

    documents = load_pdf("temp.pdf")

    chunks = split_documents(documents)

    embeddings = create_embeddings()

    vector_store = create_vector_store(
        chunks,
        embeddings
    )

    return documents, chunks, vector_store


with st.sidebar:

    st.header("📄 Document")

    uploaded_file = st.file_uploader(
        "Upload your PDF",
        type=["pdf"]
    )

    st.divider()

    if st.session_state.chat_history:

        if st.button(
            "🗑️ Clear Conversation",
            use_container_width=True
        ):

            st.session_state.chat_history = []

            st.rerun()




if uploaded_file is not None:
    st.info(
        f"📄 **{uploaded_file.name}**"
    )

    pdf_bytes = uploaded_file.getvalue()

    pdf_hash = hashlib.md5(pdf_bytes).hexdigest()

    # Check if user uploaded a different PDF
    if st.session_state.current_pdf_hash != pdf_hash:

        # Clear old conversation
        st.session_state.chat_history = []

        # Store new PDF hash
        st.session_state.current_pdf_hash = pdf_hash


    # Process PDF
    try:
     documents, chunks, vector_store = process_pdf(
        pdf_bytes,
        pdf_hash
    )

    except Exception :
      st.error("❌ Failed to process the PDF.")
      st.caption("Please try another PDF.")
      st.stop()
    if not documents or not chunks:
     st.warning(
        "⚠️ This PDF does not contain readable text."
    )
     st.info(
        "Please upload a text-based PDF instead of a scanned image PDF."
    )
     st.stop()

    st.success(
    f"✅ Ready to chat — {len(documents)} page(s) processed."
)


    # QUESTION INPUT
    with st.form("question_form"):

        question = st.text_input(
            "💬 Ask a question about your PDF"
        )

        submitted = st.form_submit_button("Ask")


    # PROCESS QUESTION
       
    if submitted and question:

        try:

            with st.spinner("🤖 Thinking..."):

                # Create LLM
                llm = create_llm()

                # Rewrite question using conversation history
                search_question = rewrite_question(
                    llm,
                    question,
                    st.session_state.chat_history
                )

                # Retrieve relevant chunks
                results_with_scores = (
                    vector_store.similarity_search_with_score(
                        search_question,
                        k=3
                    )
                )

                # Similarity threshold
                THRESHOLD = 1.6

                best_score = results_with_scores[0][1]

                # Check relevance
                if best_score > THRESHOLD:

                    st.warning(
                        "I couldn't find this information in the PDF."
                    )

                    st.stop()

                # Keep relevant results
                results = [
                    doc
                    for doc, score in results_with_scores
                    if score <= THRESHOLD
                ]

                # Combine retrieved chunks
                context = "\n\n".join(
                    result.page_content
                    for result in results
                )

                # Generate answer
                answer = generate_answer(
                    llm,
                    question,
                    context
                )

        except Exception:

            st.error(
                "❌ Something went wrong while generating the answer."
            )

            st.info(
                "Please try asking the question again."
            )

            st.stop()


        # Display answer
        st.subheader("🤖 Answer")
        st.write(answer)


        # Display sources
        with st.expander("📚 Sources"):

            for result in results:

                page_number = (
                    result.metadata.get("page", 0) + 1
                )

                st.markdown(
                    f"**📄 Page {page_number}**"
                )

                st.caption(
                    result.page_content
                )


        # Save conversation
        st.session_state.chat_history.append({
            "question": question,
            "answer": answer
        })
   

  
if st.session_state.chat_history:

    st.subheader("💬 Conversation")

    for chat in st.session_state.chat_history:

        st.chat_message("user").write(
            chat["question"]
        )

        st.chat_message("assistant").write(
            chat["answer"]
        )

       