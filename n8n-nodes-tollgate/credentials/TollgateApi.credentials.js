'use strict';

/**
 * Tollgate API credential — consumer label or id:secret.
 * No provider keys (DeepSeek/Brave/…) live in n8n.
 */
class TollgateApi {
	constructor() {
		this.name = 'tollgateApi';
		this.displayName = 'Tollgate API';
		this.documentationUrl =
			'https://github.com/landjunge/TollGate/blob/main/docs/N8N.md';
		this.properties = [
			{
				displayName: 'Base URL',
				name: 'baseUrl',
				type: 'string',
				default: 'http://127.0.0.1:8787',
				required: true,
				description:
					'Tollgate root without trailing slash. From Docker n8n use http://host.docker.internal:8787',
			},
			{
				displayName: 'Consumer Key',
				name: 'apiKey',
				type: 'string',
				typeOptions: { password: true },
				default: 'n8n',
				required: true,
				description:
					'Open mode: any label (e.g. n8n). Auth mode: id:secret from `tollgate consumer-add n8n`',
			},
		];
		this.authenticate = {
			type: 'generic',
			properties: {
				headers: {
					Authorization: '=Bearer {{$credentials.apiKey}}',
					'X-Consumer-Key': '={{$credentials.apiKey}}',
				},
			},
		};
		this.test = {
			request: {
				baseURL: '={{$credentials.baseUrl}}',
				url: '/v1/health',
				method: 'GET',
			},
		};
	}
}

module.exports = { TollgateApi };
