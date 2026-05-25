import pytest
from unittest.mock import patch
from src.tools.linkedin_tool import LinkedInTool

@patch('src.tools.linkedin_tool.query')
def test_linkedin_tool_regex_deduplication(mock_query):

    # check same url with different tracking params 
    job_with_tracking_a = {
        'jobUrl': 'https://www.linkedin.com/jobs/view/12345/?refId=abc',
        'position': 'DevOps Engineer 1',
        'company': 'FunnyName Company'
    }
    
    job_with_tracking_b = {
        'jobUrl': 'https://www.linkedin.com/jobs/view/12345/?trackingId=xyz',
        'position': 'DevOps Engineer 2',
        'company': 'FunnyName Company'
    }
    
    mock_query.return_value = [job_with_tracking_a, job_with_tracking_b]
    
    tool = LinkedInTool()
    results = tool._run()

    assert len(results) == 1
    assert results[0]['jobUrl'] == 'https://www.linkedin.com/jobs/view/12345/'
    assert results[0]['position'] == 'DevOps Engineer 1'

@patch('src.tools.linkedin_tool.query')
def test_linkedin_tool_different_jobs_kept(mock_query):

    # check different urls with different job ids are kept
    job_1 = {'jobUrl': 'https://www.linkedin.com/jobs/view/111', 'position': 'DevOps', 'company': 'FunnyName Company'}
    job_2 = {'jobUrl': 'https://www.linkedin.com/jobs/view/222', 'position': 'DevOps', 'company': 'FunnyName Company'}
    
    mock_query.return_value = [job_1, job_2]
    
    tool = LinkedInTool()
    results = tool._run()
    
    assert len(results) == 2

@patch('src.tools.linkedin_tool.query')
def test_linkedin_tool_fallback_on_weird_url(mock_query):
    """ edge case: if url format weird, fallback & keep the firdst one """

    weird_job_1 = {'jobUrl': 'https://linkedin.com/some-weird-url?param=1', 'position': 'CEO'}
    weird_job_2 = {'jobUrl': 'https://linkedin.com/some-weird-url?param=2', 'position': 'CEO'}
    
    mock_query.return_value = [weird_job_1, weird_job_2]
    
    tool = LinkedInTool()
    results = tool._run()
    
    assert len(results) == 1
    assert results[0]['jobUrl'] == 'https://linkedin.com/some-weird-url'