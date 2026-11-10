package org.apache.poi.ss.usermodel;
public interface Workbook extends java.io.Closeable, Iterable<Sheet> { Sheet getSheet(String name); }
