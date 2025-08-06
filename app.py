import json
import os
import uuid
from flask import Flask, jsonify, redirect, render_template, request, session, url_for, abort
from openai import OpenAI
from db import get_db, init_db


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")

    # Initialise database
    init_db()

    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL"),
    )

    default_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    # ---------- UI ROUTES ----------
    @app.route("/")
    def index():
        conn = get_db()
        agents = conn.execute("SELECT * FROM agents").fetchall()
        conn.close()
        return render_template("agent_list.html", agents=agents)

    @app.route("/agents/new", methods=["GET", "POST"])
    def create_agent():
        if request.method == "POST":
            name = request.form["name"]
            model = request.form.get("model", default_model)
            instructions = request.form.get("instructions", "")
            tools = request.form.get("tools", "")
            guardrails = request.form.get("guardrails", "")
            conn = get_db()
            conn.execute(
                "INSERT INTO agents (name, model, instructions, tools, guardrails) VALUES (?,?,?,?,?)",
                (name, model, instructions, tools, guardrails),
            )
            conn.commit()
            conn.close()
            return redirect(url_for("index"))
        return render_template("agent_form.html", agent=None, default_model=default_model)

    @app.route("/agents/<int:agent_id>/edit", methods=["GET", "POST"])
    def edit_agent(agent_id: int):
        conn = get_db()
        agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        if not agent:
            conn.close()
            abort(404)
        if request.method == "POST":
            name = request.form["name"]
            model = request.form.get("model", default_model)
            instructions = request.form.get("instructions", "")
            tools = request.form.get("tools", "")
            guardrails = request.form.get("guardrails", "")
            conn.execute(
                "UPDATE agents SET name=?, model=?, instructions=?, tools=?, guardrails=? WHERE id=?",
                (name, model, instructions, tools, guardrails, agent_id),
            )
            conn.commit()
            conn.close()
            return redirect(url_for("index"))
        conn.close()
        return render_template("agent_form.html", agent=agent, default_model=default_model)

    @app.route("/agents/<int:agent_id>/delete", methods=["POST"])
    def delete_agent(agent_id: int):
        conn = get_db()
        conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))
        conn.execute("DELETE FROM chats WHERE agent_id=?", (agent_id,))
        conn.commit()
        conn.close()
        return redirect(url_for("index"))

    @app.route("/playground/<int:agent_id>", methods=["GET", "POST"])
    def playground(agent_id: int):
        conn = get_db()
        agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        if not agent:
            conn.close()
            abort(404)
        conversation_id = session.get("conversation_id")
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            session["conversation_id"] = conversation_id
        if request.method == "POST":
            user_msg = request.form["message"]
            messages = [
                {"role": "system", "content": agent["instructions"]},
                {"role": "user", "content": user_msg},
            ]
            tools = json.loads(agent["tools"]) if agent["tools"] else None
            response = client.chat.completions.create(
                model=agent["model"], messages=messages, tools=tools
            )
            reply = response.choices[0].message.content
            conn.execute(
                "INSERT INTO chats (agent_id, conversation_id, role, content) VALUES (?,?,?,?)",
                (agent_id, conversation_id, "user", user_msg),
            )
            conn.execute(
                "INSERT INTO chats (agent_id, conversation_id, role, content) VALUES (?,?,?,?)",
                (agent_id, conversation_id, "assistant", reply),
            )
            conn.commit()
        chats = conn.execute(
            "SELECT role, content FROM chats WHERE agent_id=? AND conversation_id=? ORDER BY id",
            (agent_id, conversation_id),
        ).fetchall()
        conn.close()
        return render_template("playground.html", agent=agent, chats=chats)

    # ---------- API ROUTES ----------
    @app.route("/api/agents", methods=["GET"])
    def api_list_agents():
        conn = get_db()
        agents = conn.execute("SELECT * FROM agents").fetchall()
        conn.close()
        return jsonify([dict(agent) for agent in agents])

    @app.route("/api/agents/<int:agent_id>", methods=["GET"])
    def api_get_agent(agent_id: int):
        conn = get_db()
        agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        conn.close()
        if not agent:
            return jsonify({"error": "not found"}), 404
        return jsonify(dict(agent))

    @app.route("/api/agents", methods=["POST"])
    def api_create_agent():
        data = request.json
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO agents (name, model, instructions, tools, guardrails) VALUES (?,?,?,?,?)",
            (
                data.get("name"),
                data.get("model", default_model),
                data.get("instructions", ""),
                json.dumps(data.get("tools")) if data.get("tools") else "",
                json.dumps(data.get("guardrails")) if data.get("guardrails") else "",
            ),
        )
        conn.commit()
        agent_id = cur.lastrowid
        conn.close()
        return jsonify({"id": agent_id}), 201

    @app.route("/api/agents/<int:agent_id>", methods=["PUT"])
    def api_update_agent(agent_id: int):
        data = request.json
        conn = get_db()
        conn.execute(
            "UPDATE agents SET name=?, model=?, instructions=?, tools=?, guardrails=? WHERE id=?",
            (
                data.get("name"),
                data.get("model", default_model),
                data.get("instructions", ""),
                json.dumps(data.get("tools")) if data.get("tools") else "",
                json.dumps(data.get("guardrails")) if data.get("guardrails") else "",
                agent_id,
            ),
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})

    @app.route("/api/agents/<int:agent_id>", methods=["DELETE"])
    def api_delete_agent(agent_id: int):
        conn = get_db()
        conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))
        conn.execute("DELETE FROM chats WHERE agent_id=?", (agent_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "deleted"})

    @app.route("/api/chat/<int:agent_id>", methods=["POST"])
    def api_chat(agent_id: int):
        data = request.json or {}
        messages = data.get("messages", [])
        conversation_id = data.get("conversation_id", str(uuid.uuid4()))
        conn = get_db()
        agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        if not agent:
            conn.close()
            return jsonify({"error": "agent not found"}), 404
        full_messages = [{"role": "system", "content": agent["instructions"]}] + messages
        tools = json.loads(agent["tools"]) if agent["tools"] else None
        response = client.chat.completions.create(
            model=agent["model"], messages=full_messages, tools=tools
        )
        reply = response.choices[0].message
        for msg in messages:
            conn.execute(
                "INSERT INTO chats (agent_id, conversation_id, role, content) VALUES (?,?,?,?)",
                (agent_id, conversation_id, msg["role"], msg["content"]),
            )
        conn.execute(
            "INSERT INTO chats (agent_id, conversation_id, role, content) VALUES (?,?,?,?)",
            (agent_id, conversation_id, reply.role, reply.content),
        )
        conn.commit()
        conn.close()
        return jsonify(
            {
                "id": response.id,
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": reply.role,
                            "content": reply.content,
                        },
                    }
                ],
                "conversation_id": conversation_id,
            }
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000)
