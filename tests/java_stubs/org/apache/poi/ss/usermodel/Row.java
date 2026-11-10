package org.apache.poi.ss.usermodel;
public interface Row extends Iterable<Cell> { int getRowNum(); Cell getCell(int i); }
