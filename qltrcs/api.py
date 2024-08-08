import requests
import os
import time
from ._util import verify_survey_id, verify_user_id, load_qualtrics_config_file, QualtricsException

class QualtricsAPIAgent:
    def __init__(self,api_token=None,data_center=None): 
        if api_token is None:
            api_token = os.environ.get('QUALTRICS_API_TOKEN')
        if data_center is None:
            data_center = os.environ.get('QUALTRICS_DATA_CENTER')
        self.api_token = api_token
        self.data_csenter = data_center
        
    @property
    def url_prefix(self):
        return f"https://{self.data_center}.qualtrics.com/API/v3/"
        
    @property
    def headers(self):
        """
        Default headers to send to Qualtrics API
        """
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-TOKEN": self.api_token,
            }
        
    def send_api_request(self,path,method,headers=None,retry=0,max_retries=5,delay=10,**kwargs):
        """
        Generic method for sending requests to the Qualtrics API.
        
        Paramters:
        - path [type: string]: The path to the API endpoint (e.g. '/whoami', '/users/{userId}', etc.)
        - method [type: string]: The HTTP method to use (e.g. 'GET', 'POST', 'PUT', or 'DELETE'.)
        - headers: [type: dict]: A dictionary of HTTP headers to include in the request. If None,
            the default headers will be used (see self.headers above).
        - timeout [type: float]: The number of seconds to wait for a response before timing out.
            This parameter can usually be ignored for most requests.
        - **kwargs: Additional keyword arguments to pass to the requests.request method.
        
        Returns:
        - requests.Response: The response object returned by the requests library.
        """
        if isinstance(headers,dict):
            headers = {**self.headers,**headers}
        else:
            headers = self.headers
        
        if not path.startswith('http'):
            url = self.url_prefix + path
        else:
            url = path
        response = requests.request(method,url,headers=headers,**kwargs)
        if response.status_code in [500,503,504] and retry <= max_retries:
            return self.send_api_request(path,method,headers=headers,max_retries=max_retries,retry=retry+1,delay=delay,**kwargs)
        if response.status_code == 429 and retry <= max_retries:
            wait_time = delay*(2**retry)
            time.sleep(wait_time)
            return self.send_api_request(path,method,headers=headers,max_retries=max_retries,retry=retry+1,delay=delay,**kwargs)
        if not response.ok:
            raise QualtricsException(response)
        return response
    
    def whoami(self):
        """
        Who Am I: Determine the user ID and other user information associated with 
        an Qualtrics API token or a Qualtrics OAuth access token.
        
        Parameters:
        - None
        
        Returns:
        - JSON (dict): An object containing the user's ID and other information.
        """
        response = self.send_api_request('/whoami','GET')
        return response.json()['result']
    
    def lookup_user(self,username):
        """
        Look Up User: Retrieve the user ID for a user with the given username.
        
        Parameters:
        - username [type: string]: The username of the user to look up. (For Kellogg-NU users,
        this is the same as their email address).
        
        Returns:
        - JSON (dict): An object containing the user's ID and other information.
        """
        response = self.send_api_request('/users/','GET',params={'username':username})
        return response.json()['result']
    
    def get_user(self,user_id):
        assert verify_user_id(user_id)
        response = self.send_api_request(f'/users/{user_id}','GET')
        return response.json()['result']
    
    def list_users_at_offset(self,offset=0):
        """
        List Users at Offset: Return a list of all users in the collection, 
        starting at the given offset.
        """
        params = {'offset':max(int(offset),0)}
        response = self.send_api_request('/users','GET',params=params)
        surveys = response.json()['result']['elements']
        nextPage = response.json()['result']['nextPage']
        return surveys, nextPage
    
    def list_users(self):
        """
        List Users: Return a list of all users in the collection.
        """
        response = self.send_api_request('/users','GET')
        users = response.json()['result']['elements']
        nextPage = response.json()['result'].get('nextPage')
        while nextPage is not None:
            response = self.send_api_request(nextPage,'GET')
            users.extend(response.json()['result']['elements'])
            nextPage = response.json()['result'].get('nextPage')
        return users
    
    def get_survey(self,survey_id):
        """
        Get Surveßy: Retrieves the details of a survey with the given ID.

        Parameters:
        - surveyId [type: string ^SV_[0-9a-zA-Z]{11,15}$]: The unique identifier for this survey
        
        Returns:
        - JSON (dict): An object containing the full survey definition.
        """
        assert verify_survey_id(survey_id)
        response = self.send_api_request(f'/surveys/{survey_id}','GET')
        return response.json()['result']
    
    def list_surveys(self,first_page_only=False):
        """
        List Surveys: Returns a list of all surveys, including metadata.
        
        Parameters:
        - first_page_only [type: bool, default=False]: If True, only the first page of surveys will be returned.
            (Mostly used for debugging.)
        """
        response = self.send_api_request('/surveys','GET')
        surveys = response.json()['result']['elements']
        nextPage = response.json()['result']['nextPage']
        if nextPage is None or first_page_only:
            return surveys
        else:
            while nextPage is not None:
                response = self.send_api_request(nextPage,'GET')
                surveys += response.json()['result']['elements']
                nextPage = response.json()['result']['nextPage']
            return surveys
        
    def export_survey(self,survey_id,format='csv',filename=None):
        """
        Export Survey: Export the responses for a survey in a specified format.
        
        Parameters:
        - surveyId [required, type: string ^SV_[0-9a-zA-Z]{11,15}$]: The unique identifier for this survey
        - format [optional, type: string, default='csv']: The format in which to export the survey responses. 
            Valid values are: 'csv', 'json', 'ndjson', 'spss', 'tsv', or 'xml'.
        - filename [optional, type: string]: The name of the file to save the exported survey responses to.
            If None, the response will be returned as a string.
            
        Returns:
        - string containing the survey responses in the specified format.
        """
        import time
        assert format in ['csv','json','ndjson','spss','tsv','xml']
        
        payload = {'format':format}

        assert verify_survey_id(survey_id)
            
        export_path = f'/surveys/{survey_id}/export-responses'
        kickoff_request = self.send_api_request(export_path,'POST',json=payload)
        
        progress_id = kickoff_request.json()['result']['progressId']
        check_request = self.send_api_request(f'{export_path}/{progress_id}','GET')
        
        wait_time = 0.5
        while check_request.json()['result']['status'] != 'complete':
            time.sleep(wait_time)
            check_request = self.send_api_request(f'{export_path}/{progress_id}','GET')
        file_id = check_request.json()['result']['fileId']
        
        
        download_request = self.send_api_request(f'{export_path}/{file_id}/file','GET')

        import zipfile
        import io
        out = ''
        with zipfile.ZipFile(io.BytesIO(download_request.content)) as survey_zip:
            for s in survey_zip.infolist():
                out += survey_zip.read(s).decode('utf-8')
                
        if filename is None:
            return out
        else:
            with open(filename,'w') as f:
                f.write(out)
            return 1
    
    def get_response_schema(self,survey_id):
        assert verify_survey_id(survey_id)
        response = self.send_api_request(f'/surveys/{survey_id}/response-schema','GET')
        return response.json()['result']

    def set_user_api_access(self,user_id,access=True):
        assert verify_user_id(user_id)
        payload = { 
                    "permissions": {
                        "controlPanel": { 
                            "accountPermissions": { 
                                "accessApi": { 
                                    "state": "on" if access else "off"
                                    } 
                                } 
                            } 
                        } 
                    }
        response = self.send_api_request(f'/users/{user_id}', 'PUT', json=payload)
        return 1
    
    def get_user_api_token(self,user_id):
        assert verify_user_id(user_id)
        try:
            response = self.send_api_request(f'users/{user_id}/apitoken','GET')
        except Exception as e:
            _ = self.send_api_request(f'users/{user_id}/apitoken','POST')
            response = self.send_api_request(f'users/{user_id}/apitoken','GET')
            
        return response.json()['result']['apiToken']
    
    def update_user_api_token(self,user_id):
        assert verify_user_id(user_id)
        response = self.send_api_request(f'users/{user_id}/apitoken','PUT')
        return response.json()['result']['apiToken']
    
    def get_user_id(self,user_id):
        response = self.get_user(user_id)
        return response.json()['result']['id']
    
    def spawn_user_agent(self, user_id):
        user_token = self.get_user_api_token(user_id)
        return QualtricsAPIAgent(api_token=user_token,data_center=self.data_center)
    