import streamlit as st
import requests



# =====================
# 配置
# =====================

API_URL = "http://127.0.0.1:8000"



st.set_page_config(
    page_title="企业知识助手",
    layout="wide"
)



# =====================
# Session状态
# =====================

if "user_id" not in st.session_state:

    st.session_state["user_id"] = None


if "username" not in st.session_state:

    st.session_state["username"] = None


if "role" not in st.session_state:

    st.session_state["role"] = None


def api_error(response, fallback="请求失败"):
    try:
        result = response.json()
        return result.get("detail") or result.get("error") or fallback
    except ValueError:
        return fallback



# =====================
# 历史记录接口
# =====================

def get_history(user_id):


    response = requests.get(

           f"{API_URL}/history/user/{user_id}"

    )


    if response.status_code == 200:

        data = response.json()


        if isinstance(data, list):

            return data


    return []



# =====================
# 登录
# =====================


def login_page():


    st.sidebar.subheader(
        "🔐 用户登录"
    )


    username = st.sidebar.text_input(
        "用户名"
    )


    password = st.sidebar.text_input(
        "密码",
        type="password"
    )


    if st.sidebar.button(
        "登录"
    ):


        response = requests.post(

            f"{API_URL}/login",

            json={

                "username": username,

                "password": password

            }

        )


        result = response.json()


        if "user_id" in result:


            st.session_state["user_id"] = result["user_id"]

            st.session_state["username"] = result["username"]

            st.session_state["role"] = result["role"]


            st.rerun()


        else:

            st.sidebar.error(
                result.get(
                    "error",
                    "登录失败"
                )
            )



# =====================
# 未登录停止
# =====================


if st.session_state["user_id"] is None:


    login_page()


    st.warning(
        "请先登录"
    )


    st.stop()



# =====================
# 主页面
# =====================


st.title(
    "🏢 企业知识助手"
)


st.sidebar.success(

    f"当前用户: {st.session_state['username']} ({st.session_state['role']})"

)



# =====================
# 历史聊天
# =====================


st.sidebar.divider()


st.sidebar.subheader(
    "🕘 历史聊天"
)



history = get_history(

    st.session_state["user_id"]

)
st.sidebar.write(
    "接口返回历史:",
    history
)


# 调试

st.sidebar.write(
    "用户ID:",
    st.session_state["user_id"]
)


st.sidebar.write(
    "历史数量:",
    len(history)
)



for item in history[:10]:


    st.sidebar.write(
        "----------------"
    )


    st.sidebar.write(
        "问题:"
    )


    st.sidebar.write(
        item["question"]
    )


    st.sidebar.write(
        "回答:"
    )


    st.sidebar.write(
        item["answer"][:80]
        +
        "..."
    )



# =====================
# 知识库管理
# =====================


st.sidebar.divider()


st.sidebar.subheader(
    "📚 知识库管理"
)



if st.session_state["role"] in ("hr", "admin"):

    role_options = ["employee", "hr"]
    if st.session_state["role"] == "admin":
        role_options.append("admin")

    document_role = st.sidebar.selectbox("文档权限", role_options)
    uploaded_file = st.sidebar.file_uploader(
        "上传文档",
        type=["pdf", "docx", "txt"],
    )

    if uploaded_file and st.sidebar.button("上传"):
        files = {
            "file": (
                uploaded_file.name,
                uploaded_file,
                uploaded_file.type,
            )
        }
        response = requests.post(
            f"{API_URL}/upload",
            files=files,
            data={
                "role": document_role,
                "user_id": st.session_state["user_id"],
            },
        )

        if response.status_code == 200:
            st.sidebar.success("上传成功")
            st.rerun()
        else:
            st.sidebar.error(api_error(response, "上传失败"))



# 文档列表


documents_response = requests.get(

    f"{API_URL}/documents",

    params={"user_id": st.session_state["user_id"]}

)



if documents_response.status_code == 200:


    documents = documents_response.json()


    for doc in documents:


        st.sidebar.write(
            "📄",
            doc["filename"]
        )


        st.sidebar.write(
            "Chunk:",
            doc["chunks"]
        )


        st.sidebar.write("权限:", doc.get("role", "employee"))


        if st.session_state["role"] in ("hr", "admin") and st.sidebar.button(

            "删除",

            key=doc["filename"]

        ):


            delete_response = requests.delete(

                f"{API_URL}/documents/{doc['filename']}",

                params={"user_id": st.session_state["user_id"]}

            )

            if delete_response.status_code == 200:
                st.rerun()
            else:
                st.sidebar.error(api_error(delete_response, "删除失败"))

elif documents_response.status_code != 200:
    st.sidebar.error(api_error(documents_response, "文档列表加载失败"))



# =====================
# 聊天
# =====================


st.divider()


st.subheader(
    "💬 智能问答"
)



question = st.text_input(
    "请输入问题"
)


if st.button("提交"):


    st.write(
        "发送用户ID:",
        st.session_state["user_id"]
    )

    response = requests.post(

        f"{API_URL}/chat",

        json={

            "question":
            question,


            "user_id":
            st.session_state["user_id"]

        }

    )



    if response.status_code == 200:


        result = response.json()



        st.subheader(
            "答案"
        )


        st.write(
            result["answer"]
        )



        st.subheader(
            "来源"
        )


        for source in result["sources"]:


            st.write(

                f"""
文件:
{source['file']}

Chunk:
{source['chunk']}
"""

            )


    else:

        st.error(
            api_error(response)
        )
