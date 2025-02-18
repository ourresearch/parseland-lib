def get_dynamodb_record(harvest_id, dynamodb):
    try:
        response = dynamodb.get_item(
            TableName='harvested-html',
            Key={
                'id': {'S': str(harvest_id)}
            }
        )

        if 'Item' not in response:
            return {'resolved_url': None, 'namespace': None}

        item = response['Item']
        return {
            'resolved_url': item.get('resolved_url', {}).get('S'),
            'namespace': item.get('native_id_namespace', {}).get('S')
        }

    except Exception as e:
        print(f"Error getting record for harvest_id {harvest_id}: {str(e)}")
        return {'resolved_url': None, 'namespace': None}