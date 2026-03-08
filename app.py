from flask import Flask, request, jsonify, render_template
import redis
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)

# ----------------- Connexion Redis -----------------
try:
    r = redis.Redis(host='redis', port=6379, decode_responses=True)
    r.ping()
    redis_available = True
except redis.exceptions.ConnectionError:
    print("Redis not available")
    r = None
    redis_available = False

# ----------------- Connexion MySQL -----------------
try:
    db = mysql.connector.connect(
        host='mysql',
        user='root',
        password='root',
        database='student_db'
    )
    cursor = db.cursor(dictionary=True)
    mysql_available = True
except Error:
    print("MySQL not available")
    db = None
    cursor = None
    mysql_available = False

# ----------------- Page principale -----------------
@app.route('/')
def home():
    return render_template('index.html')


# ----------------- Ajouter un étudiant -----------------
@app.route('/students', methods=['POST'])
def add_student():
    data = request.json
    student_id = data.get("id")

    # Vérifier si l'étudiant existe dans Redis ou MySQL
    exists_redis = redis_available and r.exists(f"student:{student_id}")
    exists_mysql = False
    if mysql_available:
        cursor.execute("SELECT 1 FROM students WHERE id=%s", (student_id,))
        exists_mysql = cursor.fetchone() is not None

    if exists_redis or exists_mysql:
        return jsonify({"error": "Student already exists"}), 400

    # Ajouter dans Redis si disponible
    if redis_available:
        r.hset(f"student:{student_id}", mapping={
            "name": data.get("name"),
            "age": data.get("age"),
            "major": data.get("major")
        })

    # Ajouter dans MySQL si disponible
    if mysql_available:
        try:
            cursor.execute(
                "INSERT INTO students (id, name, age, major) VALUES (%s, %s, %s, %s)",
                (student_id, data.get("name"), data.get("age"), data.get("major"))
            )
            db.commit()
        except Error as e:
            print("MySQL insert failed:", e)

    return jsonify({"message": "Student added"}), 201


# ----------------- Obtenir tous les étudiants -----------------
@app.route('/students', methods=['GET'])
def get_students():
    redis_students = []
    mysql_students = []

    # --- Load Redis ---
    if redis_available:
        try:
            r.execute_command("CONFIG SET slowlog-log-slower-than 0")
            keys = r.keys("student:*")
            for key in keys:
                r.execute_command("SLOWLOG RESET")
                s = r.hgetall(key)
                s["id"] = key.split(":")[1]

                slowlog = r.execute_command("SLOWLOG GET 1")
                time_us = slowlog[0][2] if slowlog else 0
                s["redis_time_us"] = time_us
                s["redis_time_ms"] = round(time_us / 1000, 3)
                redis_students.append(s)
        except redis.exceptions.ConnectionError:
            redis_students = []
    
    # --- Load MySQL ---
    if mysql_available:
        try:
            cursor.execute("SELECT id, name, age, major FROM students")
            rows = cursor.fetchall()
            for row in rows:
                row["mysql_time_ms"] = "N/A"  # Pas de mesure individuelle
                mysql_students.append(row)
        except Error:
            mysql_students = []

    # --- Si Redis down, mais MySQL ok ---
    if not redis_available and mysql_students:
        for s in mysql_students:
            redis_students.append({
                "id": str(s["id"]),
                "name": s.get("name"),
                "age": s.get("age"),
                "major": s.get("major"),
                "redis_time_ms": "N/A",
                "redis_time_us": "N/A"
            })

    # --- Si MySQL down, mais Redis ok ---
    if not mysql_available and redis_students:
        for s in redis_students:
            mysql_students.append({
                "id": s["id"],
                "name": s.get("name"),
                "age": s.get("age"),
                "major": s.get("major"),
                "mysql_time_ms": "N/A"
            })

    return jsonify({
        "redis_data": redis_students,
        "mysql_data": mysql_students
    })


# ----------------- Modifier un étudiant -----------------
@app.route('/students/<student_id>', methods=['PUT'])
def update_student(student_id):
    data = request.json

    updated = False

    # Update Redis si dispo
    if redis_available and r.exists(f"student:{student_id}"):
        r.hset(f"student:{student_id}", mapping={
            "name": data.get("name"),
            "age": data.get("age"),
            "major": data.get("major")
        })
        updated = True

    # Update MySQL si dispo
    if mysql_available:
        try:
            cursor.execute(
                "UPDATE students SET name=%s, age=%s, major=%s WHERE id=%s",
                (data.get("name"), data.get("age"), data.get("major"), student_id)
            )
            db.commit()
            if cursor.rowcount > 0:
                updated = True
        except Error:
            pass

    if not updated:
        return jsonify({"error": "Student not found"}), 404

    return jsonify({"message": "Student updated"})


# ----------------- Supprimer un étudiant -----------------
@app.route('/students/<student_id>', methods=['DELETE'])
def delete_student(student_id):
    deleted = False

    # Supprimer Redis
    if redis_available and r.exists(f"student:{student_id}"):
        r.delete(f"student:{student_id}")
        deleted = True

    # Supprimer MySQL
    if mysql_available:
        try:
            cursor.execute("DELETE FROM students WHERE id=%s", (student_id,))
            db.commit()
            if cursor.rowcount > 0:
                deleted = True
        except Error:
            pass

    if not deleted:
        return jsonify({"error": "Student not found"}), 404

    return jsonify({"message": "Student deleted"})


# ----------------- Lancer l'application -----------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)