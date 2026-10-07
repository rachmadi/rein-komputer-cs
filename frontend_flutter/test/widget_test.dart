import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/main.dart';

void main() {
  testWidgets('App loads smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const BobbyComputerApp());
    expect(find.text('Bobby Computer CS'), findsOneWidget);
  });
}
