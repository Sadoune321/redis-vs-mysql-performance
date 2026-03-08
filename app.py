from flask import Flask, request, jsonify, render_template
import redis
import mysql.connector

app = Flask(__name__)

# ----------------- Connexion Redis -----------------
r = redis.Redis(
    host='redis',
    port=6379,
    decode_responses=True
)

# ----------------- Connexion MySQL -----------------
db = mysql.connector.connect(
    host='mysql',
    user='root',
    password='root',
    database='student_db'
)
cursor = db.cursor(dictionary=True)

# ----------------- Page principale -----------------
@app.route('/')
def home():
    return render_template('index.html')


# ----------------- Ajouter un étudiant -----------------
@app.route('/students', methods=['POST'])
def add_student():
    data = request.json
    student_id = data.get("id")

    if r.exists(f"student:{student_id}"):
        return jsonify({"error": "Student already exists"}), 400

    r.hset(f"student:{student_id}", mapping={
        "name": data.get("name"),
        "age": data.get("age"),
        "major": data.get("major")
    })

    cursor.execute(
        "INSERT INTO students (id, name, age, major) VALUES (%s, %s, %s, %s)",
        (student_id, data.get("name"), data.get("age"), data.get("major"))
    )
    db.commit()

    return jsonify({"message": "Student added"}), 201


# ----------------- Obtenir tous les étudiants -----------------
@app.route('/students', methods=['GET'])
def get_students():

    # ── Redis : temps individuel par étudiant via SLOWLOG ──
    r.execute_command("CONFIG SET slowlog-log-slower-than 0")
    keys = r.keys("student:*")
    redis_students = []

    for key in keys:
        r.execute_command("SLOWLOG RESET")
        s = r.hgetall(key)
        s["id"] = key.split(":")[1]

        slowlog = r.execute_command("SLOWLOG GET 1")
        time_us = slowlog[0][2] if slowlog else 0
        s["redis_time_us"] = time_us
        s["redis_time_ms"] = round(time_us / 1000, 3)

        redis_students.append(s)

    # ── MySQL : temps individuel par étudiant via PROFILING ──
    mysql_students = []

    for s in redis_students:
        sid = s["id"]

        cursor.execute("SET profiling = 1")
        cursor.execute("SELECT id, name, age, major FROM students WHERE id = %s", (sid,))
        row = cursor.fetchone()

        cursor.execute(
            "SELECT SUM(DURATION) * 1000 AS duration_ms "
            "FROM information_schema.PROFILING "
            "WHERE QUERY_ID = (SELECT MAX(QUERY_ID) FROM information_schema.PROFILING)"
        )
        prof = cursor.fetchone()
        cursor.execute("SET profiling = 0")

        mysql_time = round(float(prof["duration_ms"]), 3) if prof and prof["duration_ms"] else 0.0

        if row:
            row["mysql_time_ms"] = mysql_time
            mysql_students.append(row)

    return jsonify({
        "redis_data": redis_students,
        "mysql_data": mysql_students,
    })


# ----------------- Modifier un étudiant -----------------
@app.route('/students/<student_id>', methods=['PUT'])
def update_student(student_id):
    data = request.json

    if not r.exists(f"student:{student_id}"):
        return jsonify({"error": "Student not found"}), 404

    r.hset(f"student:{student_id}", mapping={
        "name": data.get("name"),
        "age": data.get("age"),
        "major": data.get("major")
    })

    cursor.execute(
        "UPDATE students SET name=%s, age=%s, major=%s WHERE id=%s",
        (data.get("name"), data.get("age"), data.get("major"), student_id)
    )
    db.commit()

    return jsonify({"message": "Student updated"})


# ----------------- Supprimer un étudiant -----------------
@app.route('/students/<student_id>', methods=['DELETE'])
def delete_student(student_id):
    if not r.exists(f"student:{student_id}"):
        return jsonify({"error": "Student not found"}), 404

    r.delete(f"student:{student_id}")

    cursor.execute("DELETE FROM students WHERE id=%s", (student_id,))
    db.commit()

    return jsonify({"message": "Student deleted"})


# ----------------- Lancer l'application -----------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)