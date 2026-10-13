import 'package:flutter/material.dart';
import 'screens/chat_screen.dart';
import 'screens/login_screen.dart';
import 'screens/admin_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const BobbyComputerApp());
}

class BobbyComputerApp extends StatelessWidget {
  const BobbyComputerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Bobby Computer — Customer Care & Admin Portal',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1E40AF),
          primary: const Color(0xFF1E40AF),
          surface: Colors.white,
        ),
        scaffoldBackgroundColor: const Color(0xFFF8FAFC),
        fontFamily: null,
      ),
      initialRoute: '/',
      routes: {
        '/': (context) => const ChatScreen(),
        '/login': (context) => const LoginScreen(),
        '/admin': (context) => const AdminCatalogScreen(),
      },
    );
  }
}
