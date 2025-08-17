from flask import render_template, redirect, url_for, Response
from auth import token_required
from stream.mjpeg import gen_frames

def register_core_routes(app):
    @app.route("/")
    def home():
        return redirect(url_for("portfolio"))

    @app.route('/login', methods=['GET','POST'])
    def login():
        from flask import request, session
        import jwt, datetime
        from config import PASSWORD, SECRET_KEY

        if request.method == 'POST':
            u = request.form.get('username')
            p = request.form.get('password')
            if u == 'ismacarbo' and p == PASSWORD:
                token = jwt.encode({
                    'username': u,
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
                }, SECRET_KEY, algorithm="HS256")
                session['jwt'] = token
                return redirect(url_for('dashboard'))
            return render_template('login.html', error="Invalid credentials")
        return render_template('login.html')

    @app.route('/dashboard')
    @token_required
    def dashboard(user):
        return render_template('dashboard.html', username=user)

    @app.route('/weather')
    def weather():
        from config import OPENWEATHER_API, WINDY_API
        return render_template('weather.html', openweather_key=OPENWEATHER_API, windy_key=WINDY_API)

    @app.route('/portfolio')
    def portfolio():
        return render_template('portfolio.html')

    
    @app.route('/video_feed')
    def video_feed():
        return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

    @app.route('/objects')
    def objects():
        return """
        <html><head><title>Object Detection</title></head>
        <body>
          <h1>Object Detection Stream</h1>
          <img src="/video_feed" style="max-width:90%;"/>
        </body></html>
        """

    @app.route('/stream_face')
    @token_required
    def stream_face(user):
        return """
        <html><head><title>Face Stream</title></head>
        <body><h1>Facial Recognition Stream</h1>
        <img src="/video_feed" style="width:80%;">
        </body></html>
        """
