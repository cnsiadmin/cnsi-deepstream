from flask import Flask
from flask_restful import Resource, Api
from flask_restful import reqparse
import os, json
import threading

app = Flask(__name__)
api = Api(app)

def restart_1():
    os.system("docker exec cnsi_deepstream python3 /home/files/cnsi-deepstream/back_to_back_tracked_rtsp_1.py /home/files/cnsi-deepstream/configs/headhelmet.json &")

def restart_2():
    os.system("docker exec cnsi_deepstream python3 /home/files/cnsi-deepstream/back_to_back_tracked_rtsp_2.py /home/files/cnsi-deepstream/configs/headhelmet.json &")



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

            if args['input_rtsp1'] != None:
                json_data['input_rtsp1'] = args['input_rtsp1']
            if args['input_rtsp2'] != None:
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
            thread_1 = threading.Thread(target=restart_1)
            thread_1.start()
            thread_2 = threading.Thread(target=restart_2)
            thread_2.start()
            return {'status': 'Restart'}
        except Exception as e:
            return {'error': str(e)}

class Start(Resource):
    def get(self):
        try:
            os.system("docker restart cnsi_deepstream")
            thread_1 = threading.Thread(target=restart_1)
            thread_1.start()
            thread_2 = threading.Thread(target=restart_2)
            thread_2.start()
            return {'status': 'Start'}
        except Exception as e:
            return {'error': str(e)}

class Stop(Resource):
    def get(self):
        try:
            os.system("docker stop cnsi_deepstream")
            return {'status': 'Stop'}
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

    try:
        os.system("docker restart cnsi_deepstream")
        thread_1 = threading.Thread(target=restart_1)
        thread_1.start()
        thread_2 = threading.Thread(target=restart_2)
        thread_2.start()
    except Exception as e:
        print(e)

    app.run(debug=False, host='0.0.0.0', port=80)
