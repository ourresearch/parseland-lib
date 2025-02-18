def get_resolved_url(harvest_id, dynamodb):
    try:
        response = dynamodb.get_item(
            TableName='harvested-html',
            Key={
                'id': {'S': str(harvest_id)}
            }
        )

        if 'Item' not in response:
            return None

        if 'resolved_url' not in response['Item']:
            return None

        return response['Item']['resolved_url']['S']

    except Exception as e:
        print(f"Error getting resolved URL for harvest_id {harvest_id}: {str(e)}")
        return None


def get_namespace(harvest_id, dynamodb):
    try:
        response = dynamodb.get_item(
            TableName='harvested-html',
            Key={
                'id': {'S': str(harvest_id)}
            }
        )

        if 'Item' not in response:
            return None

        if 'native_id_namespace' not in response['Item']:
            return None

        return response['Item']['native_id_namespace']['S']

    except Exception as e:
        print(f"Error getting namespace for harvest_id {harvest_id}: {str(e)}")
        return None
