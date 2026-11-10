package org.testng;
public interface ITestResult { int SUCCESS = 1; int FAILURE = 2; int SKIP = 3; int getStatus(); ITestNGMethod getMethod(); }
