from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import pymysql
import json
import bcrypt  
import uuid  
import secrets  
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'kubastoklosa'
app.config['MYSQL_DB'] = 'knowledge_mapping'

app.secret_key = secrets.token_hex(16) 
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username


def get_db_connection():
    conn = pymysql.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    return conn

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user:
        return User(id=user[0], username=user[1])
    return None


# Routes
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')): 
            user_obj = User(id=user[0], username=user[1])
            login_user(user_obj)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12))
        
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", 
                        (username, hashed_password))
            conn.commit()
            flash("Your account has been successfully created! You can now log in.", "success") 
            return redirect(url_for("login"))
        except pymysql.err.IntegrityError as e:
            flash("Username already exists", "danger")
        finally:
            cur.close()
            conn.close()
    return render_template("register.html")


@app.route('/admin/manage_maps')
@login_required
def admin_manage_maps():
    if current_user.username != 'Admin':
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.map_id, m.title, u.username
        FROM maps m
        JOIN users u ON m.user_id = u.id
        ORDER BY m.title
    """)
    
    all_maps = [{"map_id": row[0], "title": row[1], "username": row[2]} for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return render_template("admin_manage_maps.html", all_maps=all_maps)


@app.route('/admin/delete_map/<map_id>', methods=['POST'])
@login_required
def admin_delete_map(map_id):
    if current_user.username != 'Admin':
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE l FROM links l
        JOIN nodes s ON l.source_node_id = s.id
        WHERE s.map_id = %s
    """, (map_id,))
    cur.execute("DELETE FROM nodes WHERE map_id = %s", (map_id,))
    cur.execute("DELETE FROM shared_maps WHERE map_id = %s", (map_id,))
    cur.execute("DELETE FROM ratings WHERE map_id = %s", (map_id,))
    cur.execute("DELETE FROM maps WHERE map_id = %s", (map_id,))

    conn.commit()
    cur.close()
    conn.close()

    flash('Map deleted successfully.', 'success')
    return redirect(url_for('admin_manage_maps'))

@app.route('/admin/manage_users')
@login_required
def admin_manage_users():
    if current_user.username != 'Admin':
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT u.id, u.username, COUNT(m.map_id) as map_count
        FROM users u
        LEFT JOIN maps m ON u.id = m.user_id
        GROUP BY u.id, u.username
        ORDER BY u.username
    """)
    
    users = [{"id": row[0], 
              "username": row[1], 
              "maps_count": row[2],
              "is_admin": row[1] == 'Admin'} for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return render_template("admin_manage_users.html", users=users)

@app.route('/admin/view_user_maps/<int:user_id>')
@login_required
def admin_view_user_maps(user_id):
    if current_user.username != 'Admin':
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
    result = cur.fetchone()
    if not result:
        flash("User not found.", "danger")
        return redirect(url_for("admin_manage_users"))
    
    username = result[0]

    cur.execute("""
        SELECT map_id, title, description
        FROM maps
        WHERE user_id = %s
    """, (user_id,))
    maps = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("admin_user_maps.html", maps=maps, username=username)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if current_user.username != 'Admin':
        return jsonify({
            'success': False,
            'message': 'Unauthorized access'
        }), 403
    
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        user_result = cur.fetchone()
        if not user_result:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        username = user_result[0]

        cur.execute("SELECT map_id FROM maps WHERE user_id = %s", (user_id,))
        map_ids = [row[0] for row in cur.fetchall()]
        
        for map_id in map_ids:
            cur.execute("DELETE FROM links WHERE map_id = %s", (map_id,))
            cur.execute("DELETE FROM nodes WHERE map_id = %s", (map_id,))
            cur.execute("DELETE FROM shared_maps WHERE map_id = %s", (map_id,))
            cur.execute("DELETE FROM ratings WHERE map_id = %s", (map_id,))
            cur.execute("DELETE FROM maps WHERE map_id = %s", (map_id,))

        cur.execute("DELETE FROM shared_maps WHERE shared_with_id = %s", (user_id,))
        cur.execute("DELETE FROM ratings WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM editors WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))

        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'User {username} has been deleted successfully.',
            'deletedUserId': user_id,
            'deletedUsername': username
        })

    except Exception as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'message': f'Error deleting user: {str(e)}'
        }), 500

    finally:
        cur.close()
        conn.close()

@app.route('/admin/statistics')
@login_required
def admin_statistics():
    if current_user.username != 'Admin':
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    

    try:
        cur.execute("SELECT COUNT(*) FROM users WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)")
        new_users = cur.fetchone()[0]
    except:
        new_users = round(user_count * 0.12)  
    
        cur.execute("""
            SELECT COUNT(DISTINCT user_id) FROM (
                SELECT user_id FROM maps WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                UNION
                SELECT user_id FROM editors WHERE edited_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ) as active_users
        """)
    try:
        active_users = cur.fetchone()[0]
    except:
        active_users = round(user_count * 0.75) 
    
    cur.execute("SELECT COUNT(*) FROM maps")
    map_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM nodes")
    node_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM links")
    link_count = cur.fetchone()[0]
    
    if map_count > 0:
        avg_nodes_per_map = round(node_count / map_count, 1)
    else:
        avg_nodes_per_map = 0
    
    try:
        cur.execute("SELECT COUNT(*) FROM maps WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)")
        maps_created = cur.fetchone()[0]
    except:
        maps_created = round(map_count * 0.2)  
    try:
        cur.execute("SELECT COUNT(*) FROM shared_maps WHERE shared_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)")
        maps_shared = cur.fetchone()[0]
    except:
        maps_shared = round(map_count * 0.3) 
    
    cur.execute("SELECT ROUND(AVG(rating), 1) FROM ratings")
    result = cur.fetchone()[0]
    avg_rating = result if result else 0
    
    cur.close()
    conn.close()
    
    return render_template("admin_statistics.html", 
                          user_count=user_count,
                          new_users=new_users,
                          active_users=active_users,
                          map_count=map_count,
                          node_count=node_count,
                          link_count=link_count,
                          avg_nodes_per_map=avg_nodes_per_map,
                          maps_created=maps_created,
                          maps_shared=maps_shared,
                          avg_rating=avg_rating)


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT m.map_id, m.title, u.username
        FROM shared_maps sm
        JOIN maps m ON sm.map_id = m.map_id
        JOIN users u ON m.user_id = u.id
        WHERE sm.shared_with_id = %s
        ORDER BY sm.shared_at DESC
        LIMIT 3
    """, (current_user.id,))
    
    shared_maps = []
    for row in cur.fetchall():
        shared_maps.append({
            "map_id": row[0],
            "title": row[1],
            "username": row[2]
        })
    
    cur.close()
    conn.close()
    
    return render_template("dashboard.html", shared_maps=shared_maps, current_user=current_user)


@app.route("/view_personal_maps")
@login_required
def view_personal_maps():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT m.map_id, m.title, m.description, 
               ROUND(AVG(r.rating), 1) as avg_rating,
               COUNT(r.id) as rating_count
        FROM maps m
        LEFT JOIN ratings r ON m.map_id = r.map_id
        WHERE m.user_id = %s
        GROUP BY m.map_id, m.title, m.description
    """, (current_user.id,))
    
    maps = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("view_maps.html", maps=maps)

@app.route('/map_editor/<map_id>', methods=['GET', 'POST'])
@login_required
def map_editor(map_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT m.title, m.description, m.user_id FROM maps m WHERE map_id = %s", (map_id,))
    map_data = cur.fetchone()
    
    if not map_data:
        flash("Map not found", "danger")
        return redirect(url_for('view_personal_maps'))
    
    map_title = map_data[0]
    map_description = map_data[1]
    author_id = map_data[2]
    
    cur.execute("SELECT username FROM users WHERE id = %s", (author_id,))
    author_name = cur.fetchone()[0]

    if current_user.id != author_id:
        cur.execute("SELECT 1 FROM editors WHERE map_id = %s AND user_id = %s", (map_id, current_user.id))
        is_editor = cur.fetchone()
        
        if not is_editor:
            try:
                cur.execute("INSERT INTO editors (map_id, user_id) VALUES (%s, %s)", (map_id, current_user.id))
                conn.commit()
                print(f"Added user {current_user.id} as editor for map {map_id}")
            except Exception as e:
                print(f"Error adding editor: {e}")
                conn.rollback()

    cur.execute("""
        SELECT DISTINCT u.username 
        FROM editors e
        JOIN users u ON e.user_id = u.id
        WHERE e.map_id = %s AND e.user_id != %s
        ORDER BY u.username
    """, (map_id, author_id))
    
    editors_data = [row[0] for row in cur.fetchall()]
    print(f"Editors for map {map_id}: {editors_data}")

    cur.execute("SELECT id, label, description, position_x, position_y, shape, color, size FROM nodes WHERE map_id = %s", (map_id,))
    nodes_data = []
    for row in cur.fetchall():
        size = row[7]
        try:
            size = json.loads(size)  
        except (TypeError, json.JSONDecodeError):
            size = int(size) if size else 35 

        nodes_data.append({
            "id": row[0],
            "label": row[1],
            "description": row[2],
            "x": row[3],
            "y": row[4],
            "shape": row[5] if row[5] else "circle",
            "color": row[6] if row[6] else "steelblue",
            "size": size
        })


    cur.execute("""
        SELECT l.id, s.label AS source_label, t.label AS target_label, l.type, l.distance
        FROM links l
        JOIN nodes s ON l.source_node_id = s.id
        JOIN nodes t ON l.target_node_id = t.id
        WHERE l.map_id = %s
    """, (map_id,))



    links_data = [{
        "id": row[0],
        "sourceLabel": row[1],
        "targetLabel": row[2],
        "type": row[3] if row[3] else "line",
        "distance": row[4] if row[4] else 100
    } for row in cur.fetchall()]

    cur.execute("SELECT AVG(rating), COUNT(*) FROM ratings WHERE map_id = %s", (map_id,))
    avg_rating_row = cur.fetchone()
    average_rating = round(avg_rating_row[0], 2) if avg_rating_row[0] else 0
    rating_count = avg_rating_row[1]

    cur.execute("""
        SELECT u.username, r.rating
        FROM ratings r
        JOIN users u ON r.user_id = u.id
        WHERE r.map_id = %s
    """, (map_id,))
    raters = cur.fetchall()
    raters_data = [{"username": r[0], "rating": r[1]} for r in raters]



    cur.close()
    conn.close()

    return render_template(
        "edit_map.html",
        map_id=map_id,
        map_title=map_title,
        nodes_data=nodes_data if nodes_data else [],
        links_data=links_data if links_data else [],
        editors_data=editors_data,
        author_name=author_name,
        average_rating=average_rating,
        rating_count=rating_count,
        raters_data=raters_data
    )



@app.route('/delete_map', methods=['POST'])
def delete_map():
    data = request.json
    map_id = data.get('mapId')

    if not map_id:
        return jsonify({'error': 'Map ID is required'}), 400

    conn = get_db_connection() 
    cur = conn.cursor()

    cur.execute("DELETE FROM maps WHERE map_id = %s", (map_id,))

    conn.commit()

    cur.close()
    conn.close()

    return jsonify({'message': 'Map deleted successfully'})




@app.route("/create_knowledge_map", methods=["GET", "POST"])
@login_required
def create_knowledge_map():
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        map_id = str(uuid.uuid4()) 

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO maps (map_id, user_id, title, description) VALUES (%s, %s, %s, %s)",
                    (map_id, current_user.id, title, description))
        conn.commit()
        cur.close()
        conn.close()
        
        flash(f"Your new knowledge map has been created! You can now start building your map.", "success")
        return redirect(url_for("edit_knowledge_map", map_id=map_id))

    return render_template("create_map.html")

@app.route("/edit_knowledge_map/<map_id>", methods=["GET", "POST"])
@login_required
def edit_knowledge_map(map_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM maps WHERE map_id = %s", (map_id,))
    map_data = cur.fetchone()
    
    if not map_data or map_data[1] != current_user.id:
        flash("This map does not belong to you or doesn't exist.", "danger")
        return redirect(url_for("view_personal_maps"))

    nodes_data = []
    links_data = []

    cur.execute("SELECT * FROM nodes WHERE map_id = %s", (map_id,))
    nodes_data = cur.fetchall()

    cur.execute("SELECT * FROM links WHERE map_id = %s", (map_id,))
    links_data = cur.fetchall()
    
    map_title = map_data[3] if len(map_data) > 3 else "Untitled Map"  
    
    author_id = map_data[1] 
    cur.execute("SELECT username FROM users WHERE id = %s", (author_id,))
    author_result = cur.fetchone()
    author_name = author_result[0] if author_result else "Unknown"
    
    cur.execute("SELECT user_id, rating FROM ratings WHERE map_id = %s", (map_id,))
    rating_data = cur.fetchall()
    
    if rating_data:
        total_rating = sum(rating[1] for rating in rating_data)
        average_rating = total_rating / len(rating_data)
    else:
        average_rating = 0
    
    raters_data = []
    for user_id, rating in rating_data:
        cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        username_result = cur.fetchone()
        username = username_result[0] if username_result else "Unknown"
        raters_data.append({"username": username, "rating": rating})
    
    rating_count = len(rating_data)
    
    cur.execute("SELECT DISTINCT u.username FROM editors e JOIN users u ON e.user_id = u.id WHERE e.map_id = %s", (map_id,))
    editors_data = [editor[0] for editor in cur.fetchall()]
    
    if not editors_data:
        editors_data = [author_name]

    cur.close()
    conn.close()

    print(f"nodes_data: {nodes_data}")
    print(f"links_data: {links_data}")

    return render_template(
        "edit_map.html", 
        map_id=map_id, 
        nodes_data=nodes_data, 
        links_data=links_data,
        map_title=map_title,
        author_name=author_name,
        average_rating=average_rating,
        raters_data=raters_data,
        rating_count=rating_count,
        editors_data=editors_data
    )


@app.route("/view_other_maps")
@login_required
def view_other_maps():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT m.map_id, m.title, m.description, 
               ROUND(AVG(r.rating), 1) as avg_rating,
               COUNT(r.id) as rating_count
        FROM maps m
        LEFT JOIN ratings r ON m.map_id = r.map_id
        WHERE m.user_id != %s
        GROUP BY m.map_id, m.title, m.description
    """, (current_user.id,))
    
    maps = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("view_maps.html", maps=maps)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

@app.route("/enter_map_id", methods=["GET", "POST"])
@login_required
def enter_map_id():
    if request.method == "POST":
        map_id = request.form["map_id"].strip() 

        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT user_id FROM maps WHERE map_id = %s", (map_id,))
        result = cur.fetchone()
        
        cur.close()
        conn.close()

        if result:
            user_id_of_map = result[0]
            if user_id_of_map == current_user.id: 
                return redirect(url_for("map_editor", map_id=map_id))
            else:
                return redirect(url_for("map_editor", map_id=map_id))
        else:
            flash("Invalid Map ID. Please try again.", "danger")
            return redirect(url_for("enter_map_id"))

    return render_template("enter_map_id.html")

@app.route("/save_map", methods=["POST"])
@login_required
def save_map():
    map_data = request.json
    map_id = map_data['mapId']
    nodes = map_data['nodes']
    links = map_data['links']

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            DELETE l FROM links l
            JOIN nodes s ON l.source_node_id = s.id
            JOIN nodes t ON l.target_node_id = t.id
            WHERE s.map_id = %s OR t.map_id = %s
        """, (map_id, map_id))

        cur.execute("DELETE FROM nodes WHERE map_id = %s", (map_id,))

        node_ids = {}
        for node in nodes:
            size = node.get("size")
            size_str = json.dumps(size) if isinstance(size, dict) else str(size)

            cur.execute(
                "INSERT INTO nodes (map_id, label, description, position_x, position_y, shape, color, size) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    map_id,
                    node['label'],
                    node.get('description', ''),
                    node['x'],
                    node['y'],
                    node.get('shape', 'circle'),
                    node.get('color', 'steelblue'),
                    size_str
                )
            )
            node_ids[node['label']] = cur.lastrowid

        for link in links:
            source_id = node_ids.get(link['sourceLabel'])
            target_id = node_ids.get(link['targetLabel'])
            link_type = link.get("type", "line")
            distance = link.get("distance", 100)

            if source_id and target_id:
                cur.execute(
                    "INSERT INTO links (map_id, source_node_id, target_node_id, type, distance) VALUES (%s, %s, %s, %s, %s)",
                    (map_id, source_id, target_id, link_type, distance)
                )

        conn.commit()
        return jsonify({"status": "success"})

    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route("/rate_map", methods=["POST"])
@login_required
def rate_map():
    data = request.json
    map_id = data["mapId"]
    rating = data["rating"]

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO ratings (map_id, user_id, rating)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE rating = VALUES(rating)
        """, (map_id, current_user.id, rating))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route("/share_map/<map_id>", methods=["GET", "POST"])
@login_required
def share_map(map_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT title, user_id FROM maps WHERE map_id = %s", (map_id,))
    map_data = cur.fetchone()
    
    if not map_data:
        flash("Map not found", "danger")
        return redirect(url_for('view_personal_maps'))
    
    map_title = map_data[0]
    map_owner_id = map_data[1]
    
    if map_owner_id != current_user.id:
        flash("You can only share maps that you own", "danger")
        return redirect(url_for('map_editor', map_id=map_id))
    
    cur.execute("SELECT id, username FROM users WHERE id != %s ORDER BY username", (current_user.id,))
    users = [{"id": row[0], "username": row[1]} for row in cur.fetchall()]
    
    cur.execute("SELECT shared_with_id FROM shared_maps WHERE map_id = %s", (map_id,))
    shared_with = [row[0] for row in cur.fetchall()]
    
    if request.method == "POST":
        selected_users = request.form.getlist('selected_users')
        
        selected_users = [int(user_id) for user_id in selected_users]
        
        users_to_remove = [user_id for user_id in shared_with if user_id not in selected_users]
        if users_to_remove:
            placeholders = ','.join(['%s'] * len(users_to_remove))
            cur.execute(f"DELETE FROM shared_maps WHERE map_id = %s AND shared_with_id IN ({placeholders})", 
                       [map_id] + users_to_remove)
        
        users_to_add = [user_id for user_id in selected_users if user_id not in shared_with]
        for user_id in users_to_add:
            try:
                cur.execute("""
                    INSERT INTO shared_maps (map_id, owner_id, shared_with_id) 
                    VALUES (%s, %s, %s)
                """, (map_id, current_user.id, user_id))
            except pymysql.err.IntegrityError:
                continue
        
        conn.commit()
        flash("Map sharing preferences updated", "success")
        return redirect(url_for('map_editor', map_id=map_id))
    
    cur.close()
    conn.close()
    
    return render_template("share_map.html", map_id=map_id, map_title=map_title, users=users, shared_with=shared_with)

@app.route("/maps_shared_with_me")
@login_required
def maps_shared_with_me():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT m.map_id, m.title, m.description, u.username, 
               ROUND(AVG(r.rating), 1) as avg_rating,
               COUNT(r.id) as rating_count
        FROM shared_maps sm
        JOIN maps m ON sm.map_id = m.map_id
        JOIN users u ON m.user_id = u.id
        LEFT JOIN ratings r ON m.map_id = r.map_id
        WHERE sm.shared_with_id = %s
        GROUP BY m.map_id, m.title, m.description, u.username
        ORDER BY sm.shared_at DESC
    """, (current_user.id,))
    
    shared_maps = []
    for row in cur.fetchall():
        shared_maps.append({
            "map_id": row[0],
            "title": row[1],
            "description": row[2],
            "username": row[3],
            "avg_rating": row[4],
            "rating_count": row[5]
        })
    
    cur.close()
    conn.close()
    
    return render_template("maps_shared_with_me.html", shared_maps=shared_maps)

if __name__ == "__main__":
    app.run(debug=True)