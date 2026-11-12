PROGRAM TankControl
  VAR
    FillTimer : TON;
  END_VAR
  VAR
    StartBtn AT %MX0.0 : BOOL := False;
    StopBtn AT %MX0.1 : BOOL := False;
    ResetBtn AT %MX0.2 : BOOL := False;
    LowLevel AT %MX0.3 : BOOL := False;
    HighLevel AT %MX0.4 : BOOL := False;
    Pump AT %QX1.0 : BOOL := False;
    Alarm AT %QX1.1 : BOOL := False;
    AutoMode AT %QX1.2 : BOOL := False;
  END_VAR

  (* ====================================== *)
  (* TankControl - управление резервуаром    *)
  (* ====================================== *)

  (* Сброс аварии *)
  IF ResetBtn THEN
      IF NOT (HighLevel AND NOT LowLevel) THEN
          Alarm := FALSE;
          AutoMode := FALSE;
      END_IF;
  END_IF;

  (* Запуск и остановка *)
  IF StopBtn THEN
      AutoMode := FALSE;
  ELSIF StartBtn AND NOT Alarm THEN
      AutoMode := TRUE;
  END_IF;

  (* Контроль неисправности датчиков *)
  IF HighLevel AND NOT LowLevel THEN
      Alarm := TRUE;
      AutoMode := FALSE;
  END_IF;

  (* Управление насосом с гистерезисом *)
  IF NOT AutoMode OR Alarm THEN
      Pump := FALSE;

  ELSIF HighLevel THEN
      (* Верхний уровень достигнут *)
      Pump := FALSE;

  ELSIF NOT LowLevel THEN
      (* Уровень ниже нижнего датчика *)
      Pump := TRUE;
  END_IF;

  (* Таймер максимального наполнения *)
  FillTimer(
      IN := Pump,
      PT := T#30s
  );

  (* Авария, если насос слишком долго *)
  (* работает без достижения верхнего уровня *)
  IF FillTimer.Q THEN
      Alarm := TRUE;
      AutoMode := FALSE;
      Pump := FALSE;
  END_IF;
END_PROGRAM


CONFIGURATION Config0

  RESOURCE Res0 ON PLC
    TASK task0(INTERVAL := T#20ms,PRIORITY := 1);
    PROGRAM instance0 WITH task0 : TankControl;
  END_RESOURCE
END_CONFIGURATION
