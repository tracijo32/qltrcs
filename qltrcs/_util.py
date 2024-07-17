import re
import os

def verify_survey_id(survey_id):
    assert re.match('^SV_[0-9a-zA-Z]{11,15}$', survey_id), f'Invalid survey id: {survey_id}'
    return True

def verify_user_id(user_id):
    assert re.match('^((UR)|(URH))_[0-9a-zA-Z]{11,15}$', user_id), f'Invalid user id: {user_id}'
    return True

def load_qualtrics_config_file(path_to_config=os.path.expanduser('~/.qltrcs_config')):
    with open(path_to_config) as f:
        lines = f.readlines()
    
    api_token = None
    data_center = None
    
    for line in lines:
        key, value = line.strip().replace(' ','').split('=')
        if key == 'api_token':
            api_token = value
        elif key == 'data_center':
            data_center = value
        else:
            raise ValueError(f'Invalid key in config file: {key}')
        
    if api_token is None:
        raise ValueError('api_token not found in config file')
        
    return api_token, data_center

class QualtricsException(Exception):
    def __init__(self, response):
        self.response = response
        error_message = response.json()['meta']['error']['errorMessage']
        self.message = f"Qualtrics API Error {response.status_code}: {response.reason} - {error_message}"
        super().__init__(self.message)