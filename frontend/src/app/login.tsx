import { Ionicons } from '@expo/vector-icons';
import React, { useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button, Field, InlineError } from '../components/ui';
import { useAuth } from '../lib/auth';
import { colors, radius, space } from '../lib/theme';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginScreen() {
  const { signIn, register } = useAuth();
  const [mode, setMode] = useState<'signin' | 'register'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);
  const passwordRef = useRef<TextInput>(null);

  const emailError = touched && !EMAIL_RE.test(email.trim()) ? 'Enter a valid email address' : null;
  const passwordError = touched && password.length < 8 ? 'Use at least 8 characters' : null;
  const registering = mode === 'register';

  async function submit() {
    setTouched(true);
    setError(null);
    if (!EMAIL_RE.test(email.trim()) || password.length < 8) return;
    setBusy(true);
    try {
      await (registering ? register(email, password) : signIn(email, password));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={styles.hero}>
            <View style={styles.logo}><Ionicons name="airplane" size={32} color="#fff" /></View>
            <Text accessibilityRole="header" style={styles.title}>Budget Trip Planner</Text>
            <Text style={styles.subtitle}>Tell the assistant where, how long and how much – get a day-by-day plan that fits your budget.</Text>
          </View>

          <View style={styles.form}>
            <Field
              label="Email"
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoComplete="email"
              keyboardType="email-address"
              textContentType="emailAddress"
              returnKeyType="next"
              onSubmitEditing={() => passwordRef.current?.focus()}
              error={emailError}
              testID="email"
            />
            <View style={{ gap: space.xs }}>
              <Text style={styles.label}>Password</Text>
              <View style={[styles.passwordWrap, !!passwordError && { borderColor: colors.danger }]}>
                <TextInput
                  ref={passwordRef}
                  testID="password"
                  accessibilityLabel="Password"
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry={!showPassword}
                  autoCapitalize="none"
                  autoComplete={registering ? 'new-password' : 'current-password'}
                  textContentType={registering ? 'newPassword' : 'password'}
                  returnKeyType="go"
                  onSubmitEditing={submit}
                  maxLength={72}
                  style={styles.passwordInput}
                />
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={showPassword ? 'Hide password' : 'Show password'}
                  onPress={() => setShowPassword((s) => !s)}
                  hitSlop={8}
                >
                  <Ionicons name={showPassword ? 'eye-off-outline' : 'eye-outline'} size={22} color={colors.muted} />
                </Pressable>
              </View>
              {passwordError ? <Text style={styles.errorText}>{passwordError}</Text> : null}
            </View>

            {error ? <InlineError message={error} /> : null}

            <Button
              testID="submit"
              label={registering ? 'Create account' : 'Sign in'}
              onPress={submit}
              loading={busy}
            />
            <Pressable
              accessibilityRole="button"
              onPress={() => { setMode(registering ? 'signin' : 'register'); setError(null); }}
              style={{ alignItems: 'center', padding: space.md }}
            >
              <Text style={styles.switch}>
                {registering ? 'Already have an account? ' : 'New here? '}
                <Text style={{ color: colors.primary, fontWeight: '700' }}>{registering ? 'Sign in' : 'Create an account'}</Text>
              </Text>
            </Pressable>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  scroll: { flexGrow: 1, justifyContent: 'center', padding: space.xl, gap: space.xl, maxWidth: 480, width: '100%', alignSelf: 'center' },
  hero: { alignItems: 'center', gap: space.sm },
  logo: { width: 68, height: 68, borderRadius: 20, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 26, fontWeight: '800', color: colors.text },
  subtitle: { fontSize: 15, color: colors.muted, textAlign: 'center', lineHeight: 21 },
  form: { gap: space.lg },
  label: { fontSize: 13, fontWeight: '600', color: colors.text },
  passwordWrap: {
    flexDirection: 'row', alignItems: 'center', minHeight: 46, borderWidth: 1, borderColor: colors.border,
    borderRadius: radius.md, paddingHorizontal: space.md, backgroundColor: colors.card,
  },
  passwordInput: { flex: 1, fontSize: 16, color: colors.text, minHeight: 44 },
  errorText: { color: colors.danger, fontSize: 13 },
  switch: { fontSize: 14, color: colors.muted },
});
