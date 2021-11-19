#!/usr/bin/python3

import json

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url


class VaultCloudConfigModule():
    argument_spec = dict(
        vault_addr=dict(type='str', required=True),
        role_id=dict(type='str', required=True),
        secret_id=dict(type='str', no_log=True, required=True),
        cloud_secret_name=dict(type='str', required=True),
    )
    module_kwargs = {
        'supports_check_mode': True
    }

    def __init__(self):

        self.ansible = AnsibleModule(
            self.argument_spec,
            **self.module_kwargs)
        self.params = self.ansible.params
        self.module_name = self.ansible._name
        self.exit_json = self.ansible.exit_json
        self.fail_json = self.ansible.fail_json
        self.vault_addr = None
        self.token = None

    def _fetch(self, url, method, **kwargs):
        response, info = fetch_url(
            module=self.ansible,
            url=url,
            method="POST",
            **kwargs
        )
        status = info['status']

        if status >= 400 and status != 404:
            self.fail_json(
                msg='Vault returned error',
                status_code=status
            )
        content = ""
        if response:
            content = response.read()
        return (content, status)

    def get_vault_token(self, role_id, secret_id):
        url = f"{self.vault_addr}/v1/auth/approle/login"

        data = self.ansible.jsonify(dict(
            role_id=role_id,
            secret_id=secret_id
        ))
        response, into = self._fetch(
            url, "POST", data=data
        )
        try:
            body = json.loads(response)
            token = body['auth']['client_token']
            return token
        except Exception as ex:
            self.fail_json(
                msg='Failed to process vault response',
                error=str(ex)
            )

    def _get_data(self, secret_name):
        response, info = self._fetch(
            f"{self.vault_addr}/v1/secret/data/{secret_name}",
            "GET",
            headers={
                'X-Vault-Token': self.token
            }
        )
        return json.loads(response)['data']['data']

    def __call__(self):
        self.vault_addr = self.params['vault_addr']
        role_id = self.params['role_id']
        secret_id = self.params['secret_id']
        cloud_secret_name = self.params['cloud_secret_name']
        result = {}

        self.token = self.get_vault_token(
            role_id, secret_id
        )
        cloud_data = self._get_data(cloud_secret_name)
        user_secret_name = cloud_data.pop('user_secret_name', '')
        if user_secret_name:
            # user_secret_name is found in cloud_data. Resolve it's value
            cloud_data.update(self._get_data(user_secret_name))

        try:
            cloud_config = dict(auth=dict())
            # this attrs go under 'auth'
            auth_attrs = [
                'auth_url',
                'user_domain_name', 'user_domain_id',
                'username', 'user_id', 'password',
                'project_name', 'project_id',
                'project_domain_id', 'project_domain_name',
                'domain_id', 'domain_name']
            for k, v in cloud_data.items():
                if k in auth_attrs:
                    cloud_config['auth'][k] = v
                else:
                    cloud_config[k] = v
            result = cloud_config

        except Exception as ex:
            self.fail_json(
                msg="Failed to process vault response",
                error=str(ex)
            )

        self.exit_json(
            changed=False,
            secret=result
        )


def main():
    module = VaultCloudConfigModule()
    module()


if __name__ == '__main__':
    main()