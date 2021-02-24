from flask import Flask
from flask_restful import Resource, Api
from flask_restful import reqparse
import os, json

app = Flask(__name__)
api = Api(app)

class CreateUser(Resource):
    def post(self):
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('email', type=str)
            parser.add_argument('user_name', type=str)
            parser.add_argument('password', type=str)
            args = parser.parse_args()

            _userEmail = args['email']
            _userName = args['user_name']
            _userPassword = args['password']
            return {'Email': args['email'], 'UserName': args['user_name'], 'Password': args['password']}
        except Exception as e:
            return {'error': str(e)}

class Edit(Resource):
    def get(self):
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('input_rtsp1', type=str)
            parser.add_argument('input_rtsp2', type=str)
            args = parser.parse_args()

            #config_path = '/home/files/cnsi-deepstream/configs/headhelmet.json'
            config_path = '/home/cnsi/prj/docker/cnsi-deepstream/configs/headhelmet.json'
            with open(config_path, 'r') as f:
                json_data = json.load(f)

            json_data['input_rtsp1'] = args['input_rtsp1']
            json_data['input_rtsp2'] = args['input_rtsp2']

            with open(config_path, 'w', encoding='utf-8') as make_file:
                json.dump(json_data, make_file, indent="\t")

            return {'input_rtsp1': args['input_rtsp1'], 'input_rtsp2': args['input_rtsp2'], 'status': 'success' }
        except Exception as e:
            return {'error': str(e)}

class Restart(Resource):
    def get(self):
        try:
            os.system("docker restart cnsi_deepstream")
            os.system("docker exec cnsi_deepstream python3 /home/files/cnsi-deepstream/back_to_back_tracked_rtsp.py /home/files/cnsi-deepstream/configs/headhelmet.json")
            return {'status': 'success'}
        except Exception as e:
            return {'error': str(e)}

class Start(Resource):
    def get(self):
        try:
            os.system("docker restart cnsi_deepstream")
            os.system("docker exec cnsi_deepstream python3 /home/files/cnsi-deepstream/back_to_back_tracked_rtsp.py /home/files/cnsi-deepstream/configs/headhelmet.json")
            return {'status': 'success'}
        except Exception as e:
            return {'error': str(e)}

class Stop(Resource):
    def get(self):
        try:
            os.system("docker stop cnsi_deepstream")
            return {'status': 'success'}
        except Exception as e:
            return {'error': str(e)}

class Reboot(Resource):
    def get(self):
        try:
            os.system("reboot")
            return {'status': 'success'}
        except Exception as e:
            return {'error': str(e)}

#api.add_resource(CreateUser, '/user')
api.add_resource(Restart, '/restart')
api.add_resource(Start, '/start')
api.add_resource(Stop, '/stop')
api.add_resource(Edit, '/edit')
api.add_resource(Reboot, '/reboot')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)
