output "instance_id" {
  value = aws_instance.portal_instance.id
}

output "public_ip" {
  value = aws_instance.portal_instance.public_ip
}

output "instance_state" {
  value = aws_instance.portal_instance.instance_state
}
