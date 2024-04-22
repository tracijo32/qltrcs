import re
import os

def verify_survey_id(survey_id):
    assert re.match('^SV_[0-9a-zA-Z]{11,15}$', survey_id), f'Invalid survey id: {survey_id}'
    return True

def verify_user_id(user_id):
    assert re.match('^((UR)|(URH))_[0-9a-zA-Z]{11,15}$', user_id), f'Invalid user id: {user_id}'
    return True

def get_qualtrics_api_token(path):
    with open(os.path.expanduser(path)) as f:
        return f.read().strip()