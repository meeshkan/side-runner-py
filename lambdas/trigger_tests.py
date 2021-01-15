import json
import boto3
from graphqlclient import GraphQLClient


def lambda_handler(event, context):


    client = GraphQLClient('https://api.8base.com/ckhqdz5mu01r307mn6szcbdke')
    client.inject_token('Bearer 972b2415-ff8f-45ab-998c-51c8e51f842a')

    result = client.execute('''
        query($id:ID!) {
          userStoriesList(filter: {
            project: {
              id:{
                equals:$id
              }
            }
          }) {
            items {
              title
              isTestCase
              flowIDs
              created
              isExpected
              recording {
                steps
              }
            }
          }
        }
    ''', variables={"id": ""})

    print(result)

    test_list = default_test_list(event["url"], event["client_id"], event["run_id"], event["pipeline_id"])

    sns = boto3.client('sns')
    for test in test_list:
        response = sns.publish(
          TopicArn='arn:aws:sns:eu-west-1:201242457561:test_tasks',
          Message=test,
        )
        print(response)

    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }


if __name__ == '__main__':
    event = {}
    context = None

    print(lambda_handler(event, context))
