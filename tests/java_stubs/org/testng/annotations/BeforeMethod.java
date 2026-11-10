package org.testng.annotations;
import java.lang.annotation.*;
@Retention(RetentionPolicy.RUNTIME) @Target(ElementType.METHOD) public @interface BeforeMethod { boolean alwaysRun() default false; }
